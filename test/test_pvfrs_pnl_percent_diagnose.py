"""
诊断交易记录 pnl_percent 为 0 的原因/比例

用途：
- 查找 pnl!=0 但 pnl_percent==0 的交易记录数量（常见于历史入库时字段名不匹配）
- 不会修改数据库
"""

from backend_api.database import SessionLocal
from backend_api.models.pvfrs_enhanced import PVFRSTradeRecordEnhanced


def main():
    with SessionLocal() as db:
        total = db.query(PVFRSTradeRecordEnhanced).count()
        zero_pct_nonzero_pnl = (
            db.query(PVFRSTradeRecordEnhanced)
            .filter(PVFRSTradeRecordEnhanced.pnl != 0)
            .filter(PVFRSTradeRecordEnhanced.pnl_percent == 0)
            .count()
        )
        print(f"总交易记录数: {total}")
        print(f\"pnl!=0 且 pnl_percent==0 的记录数: {zero_pct_nonzero_pnl}\")

        sample = (
            db.query(PVFRSTradeRecordEnhanced)
            .filter(PVFRSTradeRecordEnhanced.pnl != 0)
            .filter(PVFRSTradeRecordEnhanced.pnl_percent == 0)
            .order_by(PVFRSTradeRecordEnhanced.id.desc())
            .limit(5)
            .all()
        )
        if sample:
            print("\\n示例(最近5条)：")
            for t in sample:
                print(
                    f\"- id={t.id}, stock={t.stock_code}, entry={t.entry_price}, exit={t.exit_price}, pnl={t.pnl}, pnl_percent={t.pnl_percent}\"
                )
        else:
            print("\\n没有发现 pnl!=0 且 pnl_percent==0 的记录。")


if __name__ == "__main__":
    main()

