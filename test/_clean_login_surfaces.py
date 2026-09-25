# -*- coding: utf-8 -*-
from pathlib import Path
import re
p = Path(__file__).resolve().parents[1] / "frontend" / "login.html"
t = p.read_text(encoding="utf-8")
t2 = re.sub(r"\n?\s*<link rel=\"stylesheet\" href=\"css/ops-surfaces\.css[^\"]*\">\s*", "\n", t)
p.write_text(t2, encoding="utf-8")
print("login has ops-surfaces:", "ops-surfaces" in t2)
