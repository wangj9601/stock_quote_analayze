# -*- coding: utf-8 -*-
from sqlalchemy import create_engine, text

URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"


def main():
    eng = create_engine(URL)
    with eng.connect() as c:
        total_codes = c.execute(
            text(
                "SELECT COUNT(*) FROM stock_basic_info "
                "WHERE COALESCE(collect_enabled, TRUE) = TRUE"
            )
        ).scalar()
        fina_codes = c.execute(
            text("SELECT COUNT(DISTINCT code) FROM stock_fina_indicator")
        ).scalar()
        roe_codes = c.execute(
            text(
                "SELECT COUNT(DISTINCT code) FROM stock_fina_indicator "
                "WHERE roe IS NOT NULL OR roe_waa IS NOT NULL"
            )
        ).scalar()
        roe_rows = c.execute(
            text(
                "SELECT COUNT(*) FROM stock_fina_indicator "
                "WHERE roe IS NOT NULL OR roe_waa IS NOT NULL"
            )
        ).scalar()
        annual_roe = c.execute(
            text(
                "SELECT COUNT(DISTINCT code) FROM stock_fina_indicator "
                "WHERE (roe IS NOT NULL OR roe_waa IS NOT NULL) "
                "AND right(end_date::text, 4) = '1231'"
            )
        ).scalar()
        print(
            f"universe={total_codes} fina_codes={fina_codes} "
            f"roe_codes={roe_codes} annual_roe_codes={annual_roe} roe_rows={roe_rows}"
        )


if __name__ == "__main__":
    main()
