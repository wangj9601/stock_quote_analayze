# -*- coding: utf-8 -*-
import openpyxl, sys, io, re
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

for f in [r"reports/csv/urt_7_20261021_125949.xlsx", r"reports/csv/urt_6_20261021_130110.xlsx"]:
    wb = openpyxl.load_workbook(f, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = list(rows[0])
    data = rows[1:]
    i_sig = header.index('信号日')
    i_risk = header.index('风险')
    sigs = Counter(str(r[i_sig])[:10] for r in data)
    print(f, "信号日分布:", dict(sigs))
    c = Counter()
    for r in data:
        risk = r[i_risk] or ''
        for piece in re.split(r'[;,、]+', str(risk)):
            piece = piece.strip()
            if piece and piece not in ('无', '-'):
                c[piece] += 1
    print("风险Top6:", c.most_common(6))
    wb.close()
