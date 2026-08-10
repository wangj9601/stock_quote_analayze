#!/usr/bin/env python3
"""下载 Noto Sans SC 简体子集（fontsource WOFF）并转为 TTF，供板块分析 PDF 嵌入。"""
from __future__ import annotations

import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "assets" / "fonts"
OUT_TTF = OUT_DIR / "NotoSansSC-Subset.ttf"
WOFF_URL = (
    "https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.2.5/"
    "files/noto-sans-sc-chinese-simplified-400-normal.woff"
)


def main() -> int:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("请先安装: pip install fonttools brotli", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_DIR / "_noto-sc-download.woff"
    print(f"下载 {WOFF_URL}")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(WOFF_URL, headers={"User-Agent": "stock-quote-analayze-font-build"})
    with urllib.request.urlopen(req, context=ctx, timeout=180) as resp, tmp.open("wb") as f:
        f.write(resp.read())
    print(f"WOFF {tmp.stat().st_size} bytes -> 转换 TTF")
    font = TTFont(str(tmp))
    font.flavor = None
    font.save(str(OUT_TTF))
    tmp.unlink(missing_ok=True)
    print(f"已写入 {OUT_TTF} ({OUT_TTF.stat().st_size} bytes)")
    print("许可: SIL Open Font License 1.1 (Noto Sans SC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
