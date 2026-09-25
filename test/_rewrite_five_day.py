# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path(r"e:\wangxw\work\stock_quote_analayze\frontend\five_day_change_calculator.html")
text = path.read_text(encoding="utf-8")

new_head = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>5天升跌值计算器 - 冰枫堂</title>
    <link rel="icon" type="image/x-icon" href="favicon.ico">
    <link rel="stylesheet" href="css/common.css">
    <link rel="stylesheet" href="css/design-tokens.css">
    <link rel="stylesheet" href="css/ops-shell.css">
    <link rel="stylesheet" href="css/ops-data.css">
    <link rel="stylesheet" href="css/ops-responsive.css">
    <link rel="stylesheet" href="css/tools-calculator.css">
    <style>
        /* 结构保留：主题色由 tools-calculator.css 接管 */
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 600; }
        .form-group input, .form-group select { width: 100%; padding: 10px 12px; }
        .btn { cursor: pointer; margin-right: 8px; margin-bottom: 8px; }
        .result-box { padding: 1rem; margin-top: 1rem; min-height: 80px; }
        .progress-bar { width: 100%; height: 12px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; width: 0; transition: width 0.3s ease; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 1rem; }
        .status-card { padding: 1rem; text-align: center; }
        .status-value { font-size: 1.75rem; font-weight: 700; margin-bottom: 6px; }
        .log-container { padding: 1rem; max-height: 280px; overflow-y: auto; margin-top: 1rem; }
        .log-entry { margin-bottom: 4px; padding: 4px 0; border-bottom: 1px solid transparent; }
        .tabs { display: flex; margin-bottom: 1rem; }
        .tab { padding: 12px 20px; cursor: pointer; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .alert { padding: 12px 14px; margin-bottom: 1rem; border-left: 2px solid; }
    </style>
</head>
<body class="ops-map tools-calc-page" data-channel="quotes">
'''

# drop old doctype..body open
text2 = re.sub(r'(?s)^.*?<body[^>]*>\s*', new_head, text, count=1)
# remove emoji from h1 if present
text2 = text2.replace('📊 5天升跌值计算器', '5天升跌值计算器')
path.write_text(text2, encoding="utf-8")
print("rewrote five_day_change_calculator.html", len(text2))
