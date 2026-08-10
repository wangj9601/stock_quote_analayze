"""校验板块分析 PDF 样例可被 pypdf 提取到中文（非截图像素、非空文本）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "test" / "_tmp_board_analysis_sample.pdf"
GEN = ROOT / "test" / "generate_board_analysis_pdf_sample.mjs"


def ensure_sample() -> None:
    if SAMPLE.exists() and SAMPLE.stat().st_size > 1000:
        return
    subprocess.check_call(["node", str(GEN)], cwd=str(ROOT))


def test_pdf_chinese_extractable():
    ensure_sample()
    from pypdf import PdfReader

    reader = PdfReader(str(SAMPLE))
    assert len(reader.pages) >= 1
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    # 去空白后仍应有实质字符
    compact = "".join(text.split())
    assert len(compact) > 0, "extract_text 为空，疑似未嵌入中文字体或为纯截图"
    # 关键中文关键词（样例生成脚本写入）
    for needle in ("板块", "分析", "半导体", "中芯", "命中", "买点"):
        assert needle in text or needle in compact, f"未提取到「{needle}」，全文={text!r}"


if __name__ == "__main__":
    try:
        test_pdf_chinese_extractable()
    except Exception as e:
        print("FAIL:", e, file=sys.stderr)
        raise SystemExit(1)
    print("OK: Chinese text extractable from board analysis sample PDF")
