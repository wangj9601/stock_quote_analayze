# -*- coding: utf-8 -*-
from pathlib import Path
import pymupdf
import re

d = Path(r"C:\Users\Administrator\Downloads")
for pdf in sorted(d.glob("*CSB*4b71bb67*.pdf")) + sorted(d.glob("*CSB*066d24af*.pdf")) + sorted(
    d.glob("*CSB*d8595daa*.pdf")
):
    doc = pymupdf.open(pdf)
    text = "\n".join(page.get_text("text") for page in doc)
    # keep ascii-ish lines and numbers
    nums = re.findall(
        r"(?:20\d{2}-\d{2}-\d{2}\s*~\s*20\d{2}-\d{2}-\d{2}|[A-Za-z_]+|[0-9]+(?:\.[0-9]+)?%?|[0-9]+\.[0-9]+)",
        text,
    )
    out = Path("exported_docs") / f"pdf_nums_{pdf.stem[-20:]}.txt"
    # safer name
    tid = "unknown"
    for m in re.finditer(r"[0-9a-f]{8}", pdf.name.lower()):
        tid = m.group(0)
    out = Path("exported_docs") / f"pdf_nums_{tid}.txt"
    out.write_text(text, encoding="utf-8")
    print("===", tid, "pages", doc.page_count, "chars", len(text))
    # first numeric block
    compact = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.search(r"\d", s) or any(k in s for k in ("CSB", "BREAKOUT", "PROBE", "trace", "LPS", "MA10")):
            # filter mostly tofu
            if re.search(r"[A-Za-z0-9%~+\-×x./]", s):
                compact.append(s)
    print("\n".join(compact[:40]))
    print()
