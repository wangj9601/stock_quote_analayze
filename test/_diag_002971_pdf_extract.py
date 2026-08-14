# -*- coding: utf-8 -*-
"""Extract text from PDF report for 002971."""
from __future__ import annotations

import sys
from pathlib import Path

PDF = Path(r"c:\Users\Administrator\Downloads\个股分析_002971_和远气体_20260814.pdf")
OUT = Path(__file__).resolve().parents[1] / "test" / "_diag_002971_pdf.txt"


def main() -> int:
    if not PDF.exists():
        print("PDF_MISSING", PDF)
        return 1
    text = ""
    errors = []
    for name in ("pypdf", "PyPDF2", "fitz", "pdfminer.high_level"):
        try:
            if name == "pypdf":
                from pypdf import PdfReader

                r = PdfReader(str(PDF))
                text = "\n".join((p.extract_text() or "") for p in r.pages)
            elif name == "PyPDF2":
                from PyPDF2 import PdfReader

                r = PdfReader(str(PDF))
                text = "\n".join((p.extract_text() or "") for p in r.pages)
            elif name == "fitz":
                import fitz

                doc = fitz.open(str(PDF))
                text = "\n".join(page.get_text() for page in doc)
            else:
                from pdfminer.high_level import extract_text

                text = extract_text(str(PDF))
            if text and text.strip():
                print("OK_VIA", name, "chars", len(text))
                break
            errors.append(f"{name}: empty")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
    if not text.strip():
        print("EXTRACT_FAIL", "; ".join(errors))
        return 2
    OUT.write_text(text, encoding="utf-8")
    print("WROTE", OUT)
    # print key snippets
    keys = ["44.66", "45.01", "46.25", "52.95", "43.75", "break", "买点", "目标", "楔形"]
    for k in keys:
        if k in text:
            idx = text.find(k)
            print("---", k, "---")
            print(text[max(0, idx - 80) : idx + 120].replace("\n", " | "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
