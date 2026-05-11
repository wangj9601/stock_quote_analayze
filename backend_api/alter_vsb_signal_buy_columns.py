"""
为 volume_shrink_breakout_signals 增加买点/强度/提醒列（PostgreSQL，可重复执行）。
"""

from sqlalchemy import text

from backend_api.database import engine


def run():
    stmts = [
        "ALTER TABLE volume_shrink_breakout_signals ADD COLUMN IF NOT EXISTS signal_strength INTEGER",
        "ALTER TABLE volume_shrink_breakout_signals ADD COLUMN IF NOT EXISTS signal_strength_level VARCHAR(10)",
        "ALTER TABLE volume_shrink_breakout_signals ADD COLUMN IF NOT EXISTS buy_signal_text VARCHAR(220)",
        "ALTER TABLE volume_shrink_breakout_signals ADD COLUMN IF NOT EXISTS signal_reminders_json TEXT",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
    print("volume_shrink_breakout_signals 买点相关列已就绪。")


if __name__ == "__main__":
    run()
