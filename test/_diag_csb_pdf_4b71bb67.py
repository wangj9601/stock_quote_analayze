# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pymupdf
from sqlalchemy import text

from backend_api.database import SessionLocal

pdf = Path(r"C:\Users\Administrator\Downloads") / "CSB回测详情_CSB回测_4b71bb67_20261014.pdf"
# fallback: glob
if not pdf.exists():
    hits = list(Path(r"C:\Users\Administrator\Downloads").glob("*4b71bb67*.pdf"))
    pdf = hits[0] if hits else pdf
print("PDF", pdf, "exists", pdf.exists())

doc = pymupdf.open(pdf)
print("pages", doc.page_count)
texts = []
for i, page in enumerate(doc):
    t = page.get_text("text")
    texts.append(f"\n===== PAGE {i+1} =====\n{t}")
full = "\n".join(texts)
out = Path("exported_docs") / "CSB_backtest_4b71bb67_extract.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(full, encoding="utf-8")
print("wrote", out, "chars", len(full))
print(full[:12000])

db = SessionLocal()
print("\n=== RECENT TASKS ===")
rows = db.execute(
    text(
        """
        SELECT task_id, status, name,
               config->>'preset_id' AS preset_id,
               LEFT(CAST(created_at AS text), 19) AS created
        FROM csb_backtest_tasks
        ORDER BY created_at DESC NULLS LAST
        LIMIT 20
        """
    )
).fetchall()
for r in rows:
    print(dict(r._mapping))

# fuzzy id
print("\n=== LIKE 4b71 ===")
rows = db.execute(
    text(
        """
        SELECT task_id, status, name, config, summary
        FROM csb_backtest_tasks
        WHERE CAST(task_id AS text) ILIKE :p
        LIMIT 5
        """
    ),
    {"p": "%4b71%"},
).fetchall()
for r in rows:
    d = dict(r._mapping)
    cfg = d.get("config") or {}
    sm = d.get("summary") or {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    if isinstance(sm, str):
        sm = json.loads(sm)
    print("task", d["task_id"], d["status"], d["name"])
    print("config", {k: cfg.get(k) for k in (
        "preset_id","start_date","end_date","exit_mode","target_pct","target_pct_max",
        "horizon_days","min_score","use_trace","allowed_signal_types","defense_overrides",
        "min_touch_count","probe_min_score","max_signals_per_day","compare_hit_rate",
    )})
    if isinstance(sm, dict):
        print("summary", json.dumps({k: sm.get(k) for k in list(sm)[:40]}, ensure_ascii=False, default=str)[:4000])
db.close()
