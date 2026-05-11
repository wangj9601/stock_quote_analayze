"""
为 volume_shrink_breakout_signals 增加 phase_state_json（PostgreSQL，可重复执行）。
"""

from sqlalchemy import text

from backend_api.database import engine


def run():
    stmts = [
        "ALTER TABLE volume_shrink_breakout_signals ADD COLUMN IF NOT EXISTS phase_state_json TEXT",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
    print("volume_shrink_breakout_signals.phase_state_json 已就绪。")


if __name__ == "__main__":
    run()
