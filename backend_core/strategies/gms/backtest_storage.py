"""
GMS 回测任务与报告持久化（文件存储）
任务元数据、进度、日志与报告产物存放在 backend_core/strategies/gms/backtest_data/ 下。
"""

import json
import logging
import math
import os
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# 存储根目录（与本文件同级的 backtest_data）
_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_data")
_TASKS_DIR = os.path.join(_BASE_DIR, "tasks")
_REPORTS_DIR = os.path.join(_BASE_DIR, "reports")
_DETAILS_DIR = os.path.join(_BASE_DIR, "details")
_INDEX_FILE = os.path.join(_BASE_DIR, "task_index.json")
_INDEX_LOCK = threading.Lock()


def normalize_gms_task_id(task_id: Optional[str]) -> str:
    """
    规范化 URL/参数中的 task_id：去首尾空白，并将各类 Unicode 连字符统一为 ASCII '-'。
    复制粘贴或富文本中的 “假横线” 会导致与磁盘上 `{uuid}.json` 文件名不一致，从而查询 404。
    """
    if task_id is None:
        return ""
    s = str(task_id).strip()
    if not s:
        return ""
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212", "\uff0d"):
        s = s.replace(ch, "-")
    return s


def clamp_gms_progress(progress: Any) -> int:
    """任务进度限制在 0–100，避免计算误差或历史脏数据在界面显示超过 100%。"""

    try:
        v = int(round(float(progress)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, v))


def _ensure_dirs():
    for d in (_BASE_DIR, _TASKS_DIR, _REPORTS_DIR, _DETAILS_DIR):
        os.makedirs(d, exist_ok=True)


def _dump_json_atomic(path: str, data: Dict[str, Any]) -> None:
    """原子写入 JSON 文件，避免读到半写入内容。"""
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    content = json.dumps(data, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(3):
        try:
            os.replace(tmp, path)
            return
        except OSError as e:
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
            else:
                # 最后回退为直接覆盖，尽量保证可用
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    if os.path.isfile(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                logger.debug("JSON 原子替换失败，回退直接写入: %s", e)


def _load_index() -> Dict[str, Dict[str, Any]]:
    _ensure_dirs()
    if not os.path.isfile(_INDEX_FILE):
        return {}
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        # 容错：若出现 “Extra data”，通常是多段 JSON 被拼接在一起
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(content)
        return obj if isinstance(obj, dict) else {}
    except Exception as e:
        logger.warning("读取 task_index 失败: %s", e)
        return {}


def _save_index(index: Dict[str, Dict[str, Any]]) -> None:
    """原子写入 task_index.json。Windows 上若 replace 失败（文件被占用），重试后回退为直接覆盖。"""
    _ensure_dirs()
    tmp = _INDEX_FILE + ".tmp"
    content = json.dumps(index, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(3):
        try:
            os.replace(tmp, _INDEX_FILE)
            return
        except OSError as e:
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
            else:
                try:
                    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
                    if os.path.isfile(tmp):
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass
                    logger.debug("task_index 原子替换失败，已回退为直接写入: %s", e)
                except Exception as fallback_err:
                    logger.warning("task_index 写入失败: %s; 回退写入也失败: %s", e, fallback_err)


def _set_index_entry(task_id: str, created_at: Optional[str] = None, status: Optional[str] = None) -> None:
    """进程内锁保护下更新 task_index（原子写入）。"""
    with _INDEX_LOCK:
        index = _load_index()
        entry = index.get(task_id) or {}
        if created_at is not None:
            entry["created_at"] = created_at
        if status is not None:
            entry["status"] = status
        index[task_id] = entry
        _save_index(index)


def create_task(config: Dict[str, Any], name: Optional[str] = None) -> str:
    """创建任务记录，返回 task_id。"""
    _ensure_dirs()
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    task = {
        "task_id": task_id,
        "name": name or config.get("task_name") or f"GMS回测_{task_id[:8]}",
        "config": config,
        "status": "pending",
        "progress": 0,
        "message": "",
        "logs": [],
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "summary": None,
        "details_path": None,
        "error": None,
    }
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    _dump_json_atomic(path, task)
    _set_index_entry(task_id, created_at=now, status="pending")
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务详情。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return None
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    if not os.path.isfile(path):
        # 轮询时可能短暂缺失或 id 非法，避免刷 warning；需要排查可看 debug
        logger.debug("任务文件不存在: %s (原始 task_id=%r)", path, task_id)
        return None
    for attempt in range(2):
        try:
            with open(path, "r", encoding="utf-8") as f:
                task = json.load(f)
                if isinstance(task, dict):
                    task["progress"] = clamp_gms_progress(task.get("progress", 0))
                return task
        except json.JSONDecodeError as e:
            # 长任务轮询期间可能撞上写入瞬间，短暂重试一次
            if attempt == 0:
                time.sleep(0.03)
                continue
            tmp_path = path + ".tmp"
            if os.path.isfile(tmp_path):
                try:
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        task = json.load(f)
                        if isinstance(task, dict):
                            task["progress"] = clamp_gms_progress(task.get("progress", 0))
                        return task
                except Exception:
                    pass
            logger.warning("读取任务 %s JSON 解析失败: %s", tid, e)
            return None
        except Exception as e:
            logger.warning("读取任务 %s 失败: %s", tid, e)
            return None
    return None


def update_task_progress(task_id: str, progress: int, message: str = "", log_line: Optional[str] = None) -> bool:
    """更新任务进度与可选日志。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    task = get_task(tid)
    if not task:
        return False
    task["progress"] = clamp_gms_progress(progress)
    task["message"] = message
    if log_line is not None:
        task.setdefault("logs", []).append({"ts": datetime.utcnow().isoformat(), "text": log_line})
    if task.get("status") == "pending" and progress > 0:
        task["status"] = "running"
        if not task.get("started_at"):
            task["started_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    try:
        _dump_json_atomic(path, task)
        _set_index_entry(tid, status=task["status"])
        return True
    except Exception as e:
        logger.warning("更新任务进度失败 %s: %s", tid, e)
        return False


def append_task_log(task_id: str, log_line: str) -> bool:
    """仅追加一条日志。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    task = get_task(tid)
    if not task:
        return False
    task.setdefault("logs", []).append({"ts": datetime.utcnow().isoformat(), "text": log_line})
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    try:
        _dump_json_atomic(path, task)
        return True
    except Exception as e:
        logger.warning("追加任务日志失败 %s: %s", tid, e)
        return False


def complete_task(task_id: str, summary: Dict[str, Any], details_path: Optional[str] = None) -> bool:
    """标记任务完成并写入汇总与明细路径。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    task = get_task(tid)
    if not task:
        return False
    task["status"] = "completed"
    task["progress"] = 100
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    task["summary"] = summary
    task["details_path"] = details_path
    task["error"] = None
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    try:
        _dump_json_atomic(path, task)
        _set_index_entry(tid, status="completed")
        # 报告与任务一一对应，report_id = task_id
        report_path = os.path.join(_REPORTS_DIR, f"{tid}.json")
        report = {
            "report_id": tid,
            "task_id": tid,
            "name": task.get("name"),
            "created_at": task.get("completed_at"),
            "summary": summary,
            "details_path": details_path,
        }
        _dump_json_atomic(report_path, report)
        return True
    except Exception as e:
        logger.warning("完成任务写入失败 %s: %s", tid, e)
        return False


def fail_task(task_id: str, error: str) -> bool:
    """标记任务失败。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    task = get_task(tid)
    if not task:
        return False
    task["status"] = "failed"
    task["error"] = error
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    try:
        _dump_json_atomic(path, task)
        _set_index_entry(tid, status="failed")
        return True
    except Exception as e:
        logger.warning("失败任务写入失败 %s: %s", tid, e)
        return False


def cancel_task(task_id: str) -> bool:
    """标记任务已取消。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    task = get_task(tid)
    if not task:
        return False
    if task.get("status") in ("completed", "failed"):
        return False
    task["status"] = "cancelled"
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{tid}.json")
    try:
        _dump_json_atomic(path, task)
        _set_index_entry(tid, status="cancelled")
        return True
    except Exception as e:
        logger.warning("取消任务写入失败 %s: %s", tid, e)
        return False


def delete_task(task_id: str) -> bool:
    """删除任务及对应报告与明细文件。"""
    tid = normalize_gms_task_id(task_id)
    if not tid:
        return False
    for subdir, ext in ((_TASKS_DIR, ".json"), (_REPORTS_DIR, ".json")):
        p = os.path.join(subdir, f"{tid}{ext}")
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception as e:
                logger.warning("删除文件 %s 失败: %s", p, e)
    for ext in (".csv", ".xlsx"):
        p = os.path.join(_DETAILS_DIR, f"{tid}{ext}")
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception as e:
                logger.warning("删除文件 %s 失败: %s", p, e)
    with _INDEX_LOCK:
        index = _load_index()
        if tid in index:
            del index[tid]
            _save_index(index)
    return True


def list_tasks(status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """任务列表，按创建时间倒序。"""
    index = _load_index()
    items = []
    for tid, meta in index.items():
        if status and meta.get("status") != status:
            continue
        task = get_task(tid)
        if task:
            items.append(task)
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[offset : offset + limit]


def get_task_logs(task_id: str) -> List[Dict[str, Any]]:
    """返回任务日志列表。"""
    task = get_task(task_id)
    if not task:
        return []
    return task.get("logs") or []


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """报告列表（仅已完成任务对应的报告），按完成时间倒序。"""
    index = _load_index()
    report_ids = [tid for tid, meta in index.items() if meta.get("status") == "completed"]
    items = []
    for rid in report_ids:
        path = os.path.join(_REPORTS_DIR, f"{rid}.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                items.append(json.load(f))
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[offset : offset + limit]


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """报告详情。"""
    rid = normalize_gms_task_id(report_id)
    if not rid:
        return None
    path = os.path.join(_REPORTS_DIR, f"{rid}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("读取报告 %s 失败: %s", rid, e)
        return None


def get_details_path(report_id: str) -> Optional[str]:
    """返回明细文件绝对路径（优先 xlsx，旧任务可能为 csv），供下载。"""
    report = get_report(report_id)
    if not report:
        return None
    rel = report.get("details_path")
    if not rel:
        return None
    if os.path.isabs(rel):
        return rel if os.path.isfile(rel) else None
    return os.path.join(_DETAILS_DIR, os.path.basename(rel))


def get_detail_path_by_ext(report_id: str, ext: str) -> Optional[str]:
    """按扩展名返回明细文件绝对路径（.csv / .xlsx），文件存在则返回，否则 None。"""
    rid = normalize_gms_task_id(report_id)
    if not rid:
        return None
    e = ext.lower().strip()
    if not e.startswith("."):
        e = "." + e
    if e not in (".csv", ".xlsx"):
        return None
    p = os.path.join(_DETAILS_DIR, f"{rid}{e}")
    return p if os.path.isfile(p) else None


def normalize_gms_stock_code(code: Any, market: Any = None) -> str:
    """
    将股票代码规范为字符串：港股纯数字不足 5 位前补零，A 股不足 6 位前补零。
    兼容 int/float（如 JSON 中 981.0）以免丢失前导零。
    """
    if code is None:
        return ""
    if isinstance(code, float):
        if math.isnan(code):
            return ""
        if code.is_integer():
            code = int(code)
    s = str(code).strip()
    if not s:
        return ""
    if not s.isdigit():
        return s
    mt = str(market or "").upper()
    if "HK" in mt:
        if len(s) < 5:
            return s.zfill(5)
    elif "CN" in mt:
        if len(s) < 6:
            return s.zfill(6)
    else:
        if len(s) < 5:
            return s.zfill(5)
    return s


def format_code_for_csv_cell(code: Any, market: Any = None) -> str:
    """
    CSV 中 code 列写入值：规范化后前置制表符，Excel 直接打开时按文本显示，避免 00981 变成 981。
    """
    norm = normalize_gms_stock_code(code, market)
    if not norm:
        return ""
    return "\t" + norm


# 下载明细 CSV 表头：内部字段名 -> 中文列名（与 backtest_runner 明细结构一致）
_GMS_BACKTEST_DETAIL_CSV_HEADER_ZH: Dict[str, str] = {
    "code": "股票代码",
    "date": "信号日期",
    "market": "市场",
    "buy_type": "买点类型",
    "score_total": "信号总分",
    "entry_open": "买入价",
    "entry_close": "买入价",
    "max_high_20d": "观察期内最高价",
    "max_gain_20d": "观察期内最大涨幅",
    "hit": "是否命中目标",
}


def _gms_detail_csv_fieldnames_zh(keys: List[str]) -> List[str]:
    return [_GMS_BACKTEST_DETAIL_CSV_HEADER_ZH.get(k, k) for k in keys]


def _gms_detail_row_to_zh_row(row: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    zh_keys = _gms_detail_csv_fieldnames_zh(keys)
    return {zh_keys[i]: row.get(keys[i]) for i in range(len(keys))}


_GMS_DETAIL_DEFAULT_FIELDS: List[str] = [
    "code",
    "date",
    "market",
    "buy_type",
    "score_total",
    "entry_open",
    "max_high_20d",
    "max_gain_20d",
    "hit",
]

# Excel 列宽（字符宽度，openpyxl column_dimensions.width）
_GMS_BACKTEST_XLSX_COL_WIDTH: Dict[str, float] = {
    "股票代码": 11.0,
    "信号日期": 12.0,
    "市场": 8.0,
    "买点类型": 10.0,
    "信号总分": 10.0,
    "买入价": 12.0,
    "观察期内最高价": 16.0,
    "观察期内最大涨幅": 18.0,
    "是否命中目标": 12.0,
}


def _build_gms_detail_rows(
    details: List[Dict[str, Any]],
    *,
    code_csv_format: bool = False,
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """返回 (内部 keys, 中文表头列表, 中文键行字典列表)。"""
    if not details:
        keys = list(_GMS_DETAIL_DEFAULT_FIELDS)
        fieldnames_zh = _gms_detail_csv_fieldnames_zh(keys)
        return keys, fieldnames_zh, []
    keys = list(details[0].keys())
    fieldnames_zh = _gms_detail_csv_fieldnames_zh(keys)
    rows_out = []
    for raw in details:
        r = dict(raw)
        if "code" in r:
            if code_csv_format:
                r["code"] = format_code_for_csv_cell(r.get("code"), r.get("market"))
            else:
                r["code"] = normalize_gms_stock_code(r.get("code"), r.get("market"))
        rows_out.append(r)
    rows_zh = [_gms_detail_row_to_zh_row(r, keys) for r in rows_out]
    return keys, fieldnames_zh, rows_zh


def _sort_gms_details_for_export(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """市场（A股优先）→ 股票代码 → 信号日期。"""
    if not details:
        return []
    return sorted(
        details,
        key=lambda d: (
            0 if (d.get("market") or "") == "CN" else 1,
            str(d.get("code") or ""),
            str(d.get("date") or ""),
        ),
    )


def _gms_rows_zh_insert_blank_between_codes(
    fieldnames_zh: List[str], rows_zh: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """同一文件内按股票代码分组，组间插入空行。"""
    if not rows_zh:
        return []
    out: List[Dict[str, Any]] = []
    prev: Optional[str] = None
    for row in rows_zh:
        c = row.get("股票代码")
        c_cmp = str(c).lstrip("\t") if c is not None else ""
        if prev is not None and c_cmp != prev:
            out.append({fn: "" for fn in fieldnames_zh})
        prev = c_cmp
        out.append(row)
    return out


def _write_gms_xlsx_sheet(ws: Any, fieldnames_zh: List[str], rows_zh: List[Dict[str, Any]]) -> None:
    """写入单个工作表：表头、按代码分组空行、列宽、股票代码文本格式。"""
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    if not fieldnames_zh:
        return
    ws.append(list(fieldnames_zh))
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    hit_header = "是否命中目标"
    prev_code: Optional[str] = None
    for row_dict in rows_zh:
        c = row_dict.get("股票代码")
        c_cmp = str(c).lstrip("\t") if c is not None else ""
        if prev_code is not None and c_cmp != prev_code:
            ws.append([""] * len(fieldnames_zh))
        prev_code = c_cmp
        row_vals = []
        for h in fieldnames_zh:
            v = row_dict.get(h)
            if h == hit_header:
                if v is True:
                    v = "是"
                elif v is False:
                    v = "否"
            row_vals.append(v)
        ws.append(row_vals)

    for col_idx, header in enumerate(fieldnames_zh, start=1):
        w = _GMS_BACKTEST_XLSX_COL_WIDTH.get(header, 14.0)
        ws.column_dimensions[get_column_letter(col_idx)].width = w

    code_col_idx = None
    for i, h in enumerate(fieldnames_zh, start=1):
        if h == "股票代码":
            code_col_idx = i
            break
    if code_col_idx and ws.max_row >= 2:
        for row in range(2, ws.max_row + 1):
            ws.cell(row=row, column=code_col_idx).number_format = "@"


def save_details_csv(task_id: str, details: List[Dict[str, Any]]) -> str:
    """将明细写入 CSV：中文表头、按代码分组空行、A股区块在前、港股在后。"""
    import csv

    _ensure_dirs()
    tid = normalize_gms_task_id(task_id) or str(task_id).strip()
    fname = f"{tid}.csv"
    path = os.path.join(_DETAILS_DIR, fname)
    sorted_details = _sort_gms_details_for_export(details)
    _, fieldnames_zh, rows_zh = _build_gms_detail_rows(sorted_details, code_csv_format=True)
    hit_hdr = "是否命中目标"
    for row in rows_zh:
        if hit_hdr in row and isinstance(row[hit_hdr], bool):
            row[hit_hdr] = "是" if row[hit_hdr] else "否"
    rows_out = _gms_rows_zh_insert_blank_between_codes(fieldnames_zh, rows_zh)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_zh, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows_out)
    return fname


def save_details_xlsx(task_id: str, details: List[Dict[str, Any]]) -> str:
    """将明细写入 Excel：「A股」「港股」两个标签页，表内按股票代码分组（空行分隔），含列宽。"""
    from openpyxl import Workbook

    _ensure_dirs()
    tid = normalize_gms_task_id(task_id) or str(task_id).strip()
    fname = f"{tid}.xlsx"
    path = os.path.join(_DETAILS_DIR, fname)
    sorted_details = _sort_gms_details_for_export(details)
    _, fieldnames_zh, rows_zh = _build_gms_detail_rows(sorted_details, code_csv_format=False)
    cn_rows = [r for r in rows_zh if r.get("市场") == "CN"]
    hk_rows = [r for r in rows_zh if r.get("市场") == "HK"]

    wb = Workbook()
    wb.remove(wb.active)
    ws_cn = wb.create_sheet("A股", 0)
    _write_gms_xlsx_sheet(ws_cn, fieldnames_zh, cn_rows)
    ws_hk = wb.create_sheet("港股", 1)
    _write_gms_xlsx_sheet(ws_hk, fieldnames_zh, hk_rows)

    wb.save(path)
    return fname
