# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "factor_contrast", Path(__file__).with_name("_diag_csb_factor_contrast.py")
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
load = _mod.load

df = load("e7b3cbe0")
print("entry_pos describe\n", df["entry_pos_in_channel"].describe())
print("neg pos", int((df["entry_pos_in_channel"] < 0).sum()), "nan", int(df["entry_pos_in_channel"].isna().sum()))
print(
    "width<=2",
    int((df["channel_width_pct"] <= 2).sum()),
    "width>2",
    int((df["channel_width_pct"] > 2).sum()),
)
masks = [
    ("baseline_all", df["score"].notna()),
    ("width>2%", df["channel_width_pct"] > 2),
    ("pos>=0", df["entry_pos_in_channel"] >= 0),
    ("cushion>=0.5", df["stop_cushion_pct"] >= 0.5),
    ("touch 4-5", df["touch_count"].between(4, 5)),
    ("width>2 & pos>=0", (df["channel_width_pct"] > 2) & (df["entry_pos_in_channel"] >= 0)),
    ("width>2 & cushion>=0.5", (df["channel_width_pct"] > 2) & (df["stop_cushion_pct"] >= 0.5)),
    (
        "width>2 & pos>=0 & cushion>=0.5",
        (df["channel_width_pct"] > 2)
        & (df["entry_pos_in_channel"] >= 0)
        & (df["stop_cushion_pct"] >= 0.5),
    ),
    ("width>2 & touch 4-5", (df["channel_width_pct"] > 2) & (df["touch_count"].between(4, 5))),
    (
        "width>2 & pos>=0 & touch 4-5",
        (df["channel_width_pct"] > 2)
        & (df["entry_pos_in_channel"] >= 0)
        & (df["touch_count"].between(4, 5)),
    ),
]
for name, m in masks:
    p = df[m]
    bad = int((p["cohort2"] == "BAD").sum())
    print(
        f"{name}: n={len(p)} hit={100*p['hit'].mean():.1f}% "
        f"win={100*(p['pnl_pct']>0).mean():.1f}% avg={p['pnl_pct'].mean():.2f}% "
        f"BAD%={100*bad/len(p):.1f}%"
    )
