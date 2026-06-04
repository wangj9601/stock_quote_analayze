#!/usr/bin/env python3
"""
Markdown 文档导出工具（Pandoc）
将 .md 导出为 Word（.docx）或 PDF（.pdf）

示例:
  python tools/export_docs.py docs/GMS交易回测买卖规则说明.md -f pdf
  python tools/export_docs.py a.md b.md -f both -o exported_docs/合并文档
  python tools/export_docs.py --gms-default
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = PROJECT_ROOT / "exported_docs"


def _out(msg: str) -> None:
    """Windows 控制台 GBK 下避免 emoji 导致 UnicodeEncodeError。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ))

# 按优先级尝试（无需完整 TeX 时优先 typst / wkhtmltopdf）
PDF_ENGINE_CANDIDATES = ("typst", "wkhtmltopdf", "lualatex", "xelatex", "pdflatex")
LATEX_ENGINES = frozenset({"lualatex", "xelatex", "pdflatex"})
TOOLS_DIR = Path(__file__).resolve().parent
CHROMIUM_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
)


def check_pandoc() -> bool:
    try:
        subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def export_to_word(input_files: Sequence[str], output_file: str) -> bool:
    cmd: List[str] = ["pandoc", *input_files, "-o", output_file, "--toc", "--toc-depth=3", "--number-sections"]
    template = PROJECT_ROOT / "template.docx"
    if template.is_file():
        cmd.append(f"--reference-doc={template}")
    try:
        subprocess.run(cmd, check=True)
        _out(f"[OK] 成功导出 Word: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        _out(f"[失败] Word 导出失败: {e}")
        return False


def _which_pdf_engine(name: str) -> bool:
    """Pandoc 的 pdf-engine 名称与可执行文件名（wkhtmltopdf 等）。"""
    return shutil.which(name) is not None


def detect_pdf_engine(preferred: Optional[str] = None) -> Optional[str]:
    if preferred and preferred != "auto":
        if _which_pdf_engine(preferred):
            return preferred
        _out(f"[提示] 未找到 PDF 引擎「{preferred}」，改为自动检测…")
    for eng in PDF_ENGINE_CANDIDATES:
        if _which_pdf_engine(eng):
            return eng
    return None


def _pdf_install_hints() -> str:
    return (
        "未检测到 Pandoc 专用 PDF 引擎。任选其一安装后重试：\n"
        "  · Typst（推荐，体积小）: winget install Typst.Typst\n"
        "  · wkhtmltopdf: winget install wkhtmltopdf.wkhtmltopdf\n"
        "  · MiKTeX（含 xelatex）: winget install MiKTeX.MiKTeX\n"
        "或先导出 Word: python tools/export_docs.py <文件.md> -f docx\n"
        "（Windows 将优先用 Edge/Chrome 无头打印；否则尝试 xhtml2pdf）"
    )


def find_chromium_binary() -> Optional[Path]:
    for path in CHROMIUM_CANDIDATES:
        if path.is_file():
            return path
    return None


def _ensure_utf8_meta(html: str) -> str:
    if re.search(r'<meta[^>]+charset\s*=', html, re.IGNORECASE):
        return html
    if re.search(r"<head[^>]*>", html, re.IGNORECASE):
        return re.sub(
            r"(<head[^>]*>)",
            r'\1\n<meta charset="utf-8"/>',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"/></head><body>{html}</body></html>'


def _inject_css_into_html(html: str, css_path: Path) -> str:
    if not css_path.is_file():
        return html
    css_block = f"<style>\n{css_path.read_text(encoding='utf-8')}\n</style>"
    lower = html.lower()
    if "</head>" in lower:
        idx = lower.rfind("</head>")
        return html[:idx] + css_block + html[idx:]
    return f"<html><head>{css_block}</head><body>{html}</body></html>"


def _pandoc_to_html_file(input_files: Sequence[str], html_path: str) -> bool:
    cmd: List[str] = [
        "pandoc",
        *input_files,
        "-o",
        html_path,
        "--standalone",
        "--toc",
        "--toc-depth=3",
        "--number-sections",
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _register_cjk_font_for_xhtml2pdf() -> bool:
    """为 xhtml2pdf/reportlab 注册 TTF 中文字体（.ttc 易乱码，优先 simhei.ttf）。"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return False
    if "CJKFont" in pdfmetrics.getRegisteredFontNames():
        return True
    # (path, subfontIndex) — 仅 .ttf 用 index 0；.ttc 需指定子字体
    candidates: List[Tuple[Path, int]] = [
        (Path(r"C:\Windows\Fonts\simhei.ttf"), 0),
        (Path(r"C:\Windows\Fonts\msyh.ttc"), 0),
        (Path(r"C:\Windows\Fonts\simsun.ttc"), 0),
    ]
    for font_path, sub_idx in candidates:
        if not font_path.is_file():
            continue
        try:
            pdfmetrics.registerFont(
                TTFont("CJKFont", str(font_path), subfontIndex=sub_idx)
            )
            return True
        except Exception:
            continue
    return False


def _strip_html_styles_for_xhtml2pdf(html: str) -> str:
    """移除 Pandoc 默认样式（含 xhtml2pdf 不支持的 :not 等），避免解析失败。"""
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(
        r'<link[^>]*rel=["\']stylesheet["\'][^>]*>',
        "",
        html,
        flags=re.IGNORECASE,
    )
    return html


def export_to_pdf_via_chromium(input_files: Sequence[str], output_file: str) -> bool:
    """Pandoc -> HTML，再由 Edge/Chrome 无头 --print-to-pdf（中文可靠）。"""
    browser = find_chromium_binary()
    if not browser:
        return False

    html_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as tmp:
            html_path = tmp.name
        if not _pandoc_to_html_file(input_files, html_path):
            _out("[失败] Pandoc 生成 HTML 失败")
            return False

        html_text = _ensure_utf8_meta(Path(html_path).read_text(encoding="utf-8"))
        html_text = _inject_css_into_html(html_text, TOOLS_DIR / "export_pdf.css")
        Path(html_path).write_text(html_text, encoding="utf-8")

        pdf_abs = Path(output_file).resolve()
        pdf_abs.parent.mkdir(parents=True, exist_ok=True)
        uri = Path(html_path).resolve().as_uri()
        cmd = [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_abs}",
            uri,
        ]
        _out(f"[信息] 使用 PDF 引擎: chromium（{browser.name} 无头打印）")
        subprocess.run(cmd, check=True, timeout=120)
        if not pdf_abs.is_file() or pdf_abs.stat().st_size < 100:
            _out("[失败] 浏览器未生成有效 PDF 文件")
            return False
        _out(f"[OK] 成功导出 PDF（浏览器无头）: {pdf_abs}")
        return True
    except subprocess.TimeoutExpired:
        _out("[失败] 浏览器 PDF 导出超时")
        return False
    except subprocess.CalledProcessError as e:
        _out(f"[失败] 浏览器 PDF 导出失败: {e}")
        return False
    except Exception as e:
        _out(f"[失败] 浏览器 PDF 导出异常: {e}")
        return False
    finally:
        if html_path:
            try:
                Path(html_path).unlink(missing_ok=True)
            except OSError:
                pass


def export_to_pdf_via_xhtml2pdf(input_files: Sequence[str], output_file: str) -> bool:
    """无 typst/LaTeX/wkhtmltopdf 时：Pandoc -> HTML + xhtml2pdf（需 pip 依赖）。"""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return False
    if not _register_cjk_font_for_xhtml2pdf():
        _out("[提示] 未找到 Windows 中文字体（simhei.ttf 等），PDF 中文可能乱码")

    css_path = TOOLS_DIR / "export_pdf_xhtml2pdf.css"
    html_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as tmp:
            html_path = tmp.name
        if not _pandoc_to_html_file(input_files, html_path):
            _out("[失败] Pandoc 生成 HTML 失败")
            return False
        html_text = _strip_html_styles_for_xhtml2pdf(
            Path(html_path).read_text(encoding="utf-8")
        )
        html_text = _ensure_utf8_meta(html_text)
        html_text = _inject_css_into_html(html_text, css_path)
        Path(html_path).write_text(html_text, encoding="utf-8")
        html_text = Path(html_path).read_text(encoding="utf-8")
        with open(output_file, "wb") as pdf_file:
            status = pisa.CreatePDF(html_text, dest=pdf_file, encoding="utf-8")
        if status.err:
            _out(f"[失败] xhtml2pdf 导出失败（错误数 {status.err}）")
            return False
        _out("[OK] 成功导出 PDF（HTML + xhtml2pdf 回退）: " + output_file)
        return True
    except Exception as e:
        _out(f"[失败] xhtml2pdf 导出异常: {e}")
        return False
    finally:
        if html_path:
            try:
                Path(html_path).unlink(missing_ok=True)
            except OSError:
                pass


def export_to_pdf(
    input_files: Sequence[str],
    output_file: str,
    pdf_engine: Optional[str] = None,
) -> bool:
    pref = (pdf_engine or "auto").lower()
    if pref in ("chromium", "edge", "chrome"):
        return export_to_pdf_via_chromium(input_files, output_file)
    if pref == "html":
        _out("[信息] 使用 PDF 引擎: html（Pandoc + xhtml2pdf）")
        return export_to_pdf_via_xhtml2pdf(input_files, output_file)

    engine = detect_pdf_engine(pdf_engine or "auto")
    if not engine:
        _out("[信息] 未检测到 typst/wkhtmltopdf/LaTeX，尝试 Edge/Chrome 无头打印…")
        if export_to_pdf_via_chromium(input_files, output_file):
            return True
        _out("[信息] 浏览器不可用，尝试 xhtml2pdf 回退…")
        if export_to_pdf_via_xhtml2pdf(input_files, output_file):
            return True
        _out(f"[失败] {_pdf_install_hints()}")
        return False

    cmd: List[str] = [
        "pandoc",
        *input_files,
        "-o",
        output_file,
        "--toc",
        "--toc-depth=3",
        "--number-sections",
        f"--pdf-engine={engine}",
    ]
    if engine in LATEX_ENGINES:
        cmd.extend(
            [
                "-V",
                "geometry:margin=1in",
                "-V",
                "fontsize=12pt",
                "-V",
                "documentclass=article",
            ]
        )
        if engine in ("xelatex", "lualatex"):
            # 中文文档：优先使用系统常见字体
            cmd.extend(["-V", "CJKmainfont=Microsoft YaHei"])

    _out(f"[信息] 使用 PDF 引擎: {engine}")
    try:
        subprocess.run(cmd, check=True)
        _out(f"[OK] 成功导出 PDF: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        _out(f"[失败] PDF 导出失败（引擎 {engine}）: {e}")
        others = [x for x in PDF_ENGINE_CANDIDATES if x != engine and _which_pdf_engine(x)]
        if others:
            _out(f"可尝试指定其它已安装引擎，例如: --pdf-engine {others[0]}")
        _out(_pdf_install_hints())
        return False


def resolve_md_paths(paths: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    for p in paths:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        if not path.is_file():
            _out(f"[失败] 文件不存在或不是文件: {path}")
            sys.exit(1)
        if path.suffix.lower() != ".md":
            _out(f"[失败] 仅支持 .md 文件: {path}")
            sys.exit(1)
        resolved.append(path)
    return resolved


def parse_formats(fmt: str) -> Tuple[bool, bool]:
    f = fmt.lower()
    if f in ("word", "docx"):
        return True, False
    if f == "pdf":
        return False, True
    if f == "both":
        return True, True
    raise ValueError(f"未知格式: {fmt}")


def resolve_output_paths(
    input_paths: Sequence[Path],
    output: Optional[str],
    out_dir: Optional[str],
    want_word: bool,
    want_pdf: bool,
) -> Tuple[Optional[Path], Optional[Path]]:
    """返回 (docx_path, pdf_path)，未需要的格式为 None。"""
    if out_dir:
        base_dir = Path(out_dir).expanduser().resolve()
    elif len(input_paths) == 1 and not output:
        base_dir = input_paths[0].parent
    else:
        base_dir = DEFAULT_OUT_DIR

    if output:
        out = Path(output).expanduser()
        if not out.is_absolute():
            out = Path.cwd() / out
        out = out.resolve()
        if out.suffix.lower() in (".docx", ".pdf"):
            stem = out.with_suffix("")
            parent = out.parent
            parent.mkdir(parents=True, exist_ok=True)
            docx = parent / f"{stem.name}.docx" if want_word else None
            pdf = parent / f"{stem.name}.pdf" if want_pdf else None
            if want_word and out.suffix.lower() == ".docx":
                docx = out
            if want_pdf and out.suffix.lower() == ".pdf":
                pdf = out
            if want_word and want_pdf and out.suffix.lower() in (".docx", ".pdf"):
                other = out.with_suffix(".pdf" if out.suffix.lower() == ".docx" else ".docx")
                if out.suffix.lower() == ".docx" and want_pdf:
                    pdf = other
                elif out.suffix.lower() == ".pdf" and want_word:
                    docx = other
            return docx, pdf
        base_dir = out.parent
        base_dir.mkdir(parents=True, exist_ok=True)
        stem_name = out.name
    else:
        base_dir.mkdir(parents=True, exist_ok=True)
        if len(input_paths) == 1:
            stem_name = input_paths[0].stem
        else:
            stem_name = input_paths[0].stem + "_merged"

    docx = (base_dir / f"{stem_name}.docx") if want_word else None
    pdf = (base_dir / f"{stem_name}.pdf") if want_pdf else None
    return docx, pdf


def run_export(
    input_paths: Sequence[Path],
    fmt: str,
    output: Optional[str],
    out_dir: Optional[str],
    pdf_engine: Optional[str] = None,
) -> int:
    want_word, want_pdf = parse_formats(fmt)
    input_strs = [str(p) for p in input_paths]
    docx_out, pdf_out = resolve_output_paths(input_paths, output, out_dir, want_word, want_pdf)

    _out("输入文件:")
    for p in input_paths:
        _out(f"   - {p}")
    _out("")

    ok = 0
    if want_word and docx_out:
        if export_to_word(input_strs, str(docx_out)):
            ok += 1
    if want_pdf and pdf_out:
        if export_to_pdf(input_strs, str(pdf_out), pdf_engine=pdf_engine):
            ok += 1

    expected = (1 if want_word else 0) + (1 if want_pdf else 0)
    if ok == expected:
        _out(f"\n[OK] 导出完成（{ok}/{expected}）")
        return 0
    _out("\n[失败] 部分或全部导出失败")
    return 1


def gms_default_interactive() -> int:
    spec_dir = PROJECT_ROOT / ".kiro" / "specs" / "gms-strategy"
    requirements_file = spec_dir / "requirements.md"
    design_file = spec_dir / "design.md"
    for f in (requirements_file, design_file):
        if not f.is_file():
            _out(f"[失败] 文件不存在: {f}")
            return 1

    _out("GMS 内置文档:")
    _out(f"   - {requirements_file}")
    _out(f"   - {design_file}")
    _out("")
    _out("请选择导出格式: 1=Word  2=PDF  3=两种")
    choice = input("请输入 (1/2/3): ").strip()
    fmt_map = {"1": "word", "2": "pdf", "3": "both"}
    if choice not in fmt_map:
        _out("[失败] 无效选择")
        return 1
    return run_export(
        [requirements_file, design_file],
        fmt_map[choice],
        output=str(DEFAULT_OUT_DIR / "GMS策略完整文档"),
        out_dir=str(DEFAULT_OUT_DIR),
        pdf_engine=None,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="将 Markdown 导出为 Word / PDF（Pandoc；PDF 优先 typst 等，否则 Edge 无头 / xhtml2pdf）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/export_docs.py docs/GMS交易回测买卖规则说明.md -f pdf
  python tools/export_docs.py docs/a.md docs/b.md -f both -o exported_docs/合并
  python tools/export_docs.py report.md -f docx -o D:/out/report.docx
  python tools/export_docs.py --gms-default
        """.strip(),
    )
    p.add_argument(
        "md_files",
        nargs="*",
        metavar="FILE.md",
        help="一个或多个 .md 文件（多个时按顺序合并为一份文档）",
    )
    p.add_argument(
        "-f",
        "--format",
        choices=["word", "docx", "pdf", "both"],
        default="pdf",
        help="导出格式，默认 pdf",
    )
    p.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="输出路径：可为带扩展名的文件，或不含扩展名的主文件名（目录由 --out-dir 或默认目录决定）",
    )
    p.add_argument(
        "--out-dir",
        metavar="DIR",
        help=f"输出目录，默认 {DEFAULT_OUT_DIR}",
    )
    p.add_argument(
        "--gms-default",
        action="store_true",
        help="导出内置 .kiro/specs/gms-strategy 下的 requirements.md + design.md（交互选择格式）",
    )
    p.add_argument(
        "--pdf-engine",
        default="auto",
        metavar="ENGINE",
        help="PDF 引擎: auto | chromium/edge | html（xhtml2pdf）| typst | wkhtmltopdf | xelatex | …",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not check_pandoc():
        _out("[失败] 未找到 pandoc，请先安装: https://pandoc.org/installing.html")
        return 1

    if args.gms_default:
        if args.md_files:
            _out("[提示] 已指定 --gms-default，忽略命令行中的 md 文件参数")
        return gms_default_interactive()

    if not args.md_files:
        parser.print_help()
        _out("\n[失败] 请至少指定一个 .md 文件，或使用 --gms-default")
        return 2

    paths = resolve_md_paths(args.md_files)
    return run_export(paths, args.format, args.output, args.out_dir, pdf_engine=args.pdf_engine)


if __name__ == "__main__":
    sys.exit(main())
