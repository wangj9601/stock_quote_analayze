"""兼容入口：请优先使用 migrations/sync_industry_board_to_production.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.sync_industry_board_to_production import main

if __name__ == "__main__":
    raise SystemExit(main())
