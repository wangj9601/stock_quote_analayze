# -*- coding: utf-8 -*-
"""Re-attach ops-map CSS stack to analysis.html / stock.html (UTF-8 safe)."""
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "frontend"
VER = "20260925m"

def patch_analysis():
    p = root / "analysis.html"
    t = p.read_text(encoding="utf-8")
    assert "智能分析" in t, "analysis.html encoding broken"
    # head CSS stack
    old_head = """    <link rel="stylesheet" href="css/common.css">
    <link rel="stylesheet" href="css/analysis.css?v=20260923a">
    <link rel="stylesheet" href="css/recommend.css?v=20260913d">
    <script src="js/echarts.min.js"
        onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';"></script>
    <script>
        (function () {
            try {
                if (/(?:^|[?&])popup=1(?:&|$)/.test(String(location.search || ''))) {
                    document.documentElement.classList.add('analysis-popup-window');
                }
            } catch (e) { /* ignore */ }
        })();
    </script>
</head>

<body data-channel="analyze">"""
    new_head = f"""    <link rel="stylesheet" href="css/common.css">
    <link rel="stylesheet" href="css/design-tokens.css?v=20260925a">
    <link rel="stylesheet" href="css/ops-shell.css">
    <link rel="stylesheet" href="css/ops-data.css">
    <link rel="stylesheet" href="css/ops-responsive.css">
    <link rel="stylesheet" href="css/analysis.css?v=20260923a">
    <link rel="stylesheet" href="css/recommend.css?v=20260913d">
    <script src="js/echarts.min.js"
        onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';"></script>
    <script>
        (function () {{
            try {{
                if (/(?:^|[?&])popup=1(?:&|$)/.test(String(location.search || ''))) {{
                    document.documentElement.classList.add('analysis-popup-window');
                }}
            }} catch (e) {{ /* ignore */ }}
        }})();
    </script>
    <link rel="stylesheet" href="css/analysis-ops.css?v=20260925f">
    <link rel="stylesheet" href="css/ops-surfaces.css?v={VER}">
</head>

<body data-channel="analyze" class="ops-map">"""
    if old_head not in t:
        raise SystemExit("analysis.html head block not found")
    if "viewport-fit=cover" not in t:
        t = t.replace(
            'content="width=device-width, initial-scale=1.0"',
            'content="width=device-width, initial-scale=1.0, viewport-fit=cover"',
            1,
        )
    t = t.replace(old_head, new_head, 1)
    p.write_text(t, encoding="utf-8", newline="\n")
    print("patched analysis.html", "智能分析" in t, "ops-surfaces" in t)


def patch_stock():
    p = root / "stock.html"
    t = p.read_text(encoding="utf-8")
    assert "个股详情" in t, "stock.html encoding broken"
    old_head = """    <link rel="stylesheet" href="css/common.css">
    <link rel="stylesheet" href="css/stock.css">
    <link rel="stylesheet" href="css/analysis.css?v=20260919a">
    <script>
        (function () {
            try {
                if (/(?:^|[?&])popup=1(?:&|$)/.test(String(location.search || ''))) {
                    document.documentElement.classList.add('stock-popup-window');
                }
            } catch (e) { /* ignore */ }
        })();
    </script>
    <!-- ECharts库 - 优先使用本地文件，失败时使用CDN -->
    <script src="js/echarts.min.js"
        onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';"></script>
</head>

<body>"""
    new_head = f"""    <link rel="stylesheet" href="css/common.css">
    <link rel="stylesheet" href="css/design-tokens.css">
    <link rel="stylesheet" href="css/ops-shell.css">
    <link rel="stylesheet" href="css/ops-data.css">
    <link rel="stylesheet" href="css/ops-responsive.css">
    <link rel="stylesheet" href="css/stock.css">
    <link rel="stylesheet" href="css/analysis.css?v=20260919a">
    <link rel="stylesheet" href="css/stock-ops.css?v=20260925c">
    <script>
        (function () {{
            try {{
                if (/(?:^|[?&])popup=1(?:&|$)/.test(String(location.search || ''))) {{
                    document.documentElement.classList.add('stock-popup-window');
                }}
            }} catch (e) {{ /* ignore */ }}
        }})();
    </script>
    <!-- ECharts库 - 优先使用本地文件，失败时使用CDN -->
    <script src="js/echarts.min.js"
        onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';"></script>
    <link rel="stylesheet" href="css/ops-surfaces.css?v={VER}">
</head>

<body class="ops-map" data-channel="quotes">"""
    if old_head not in t:
        raise SystemExit("stock.html head block not found")
    if "viewport-fit=cover" not in t:
        t = t.replace(
            'content="width=device-width, initial-scale=1.0"',
            'content="width=device-width, initial-scale=1.0, viewport-fit=cover"',
            1,
        )
    t = t.replace(old_head, new_head, 1)
    p.write_text(t, encoding="utf-8", newline="\n")
    print("patched stock.html", "个股详情" in t, "ops-surfaces" in t)


if __name__ == "__main__":
    patch_analysis()
    patch_stock()
