from sqlalchemy import text


def main() -> None:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        maxd = db.execute(text("select max(date) from historical_quotes")).scalar()
        print("max historical_quotes.date =", maxd)
        if not maxd:
            return
        d = str(maxd)[:10]
        distinct_codes = db.execute(
            text("select count(distinct code) from historical_quotes where date = :d"),
            {"d": d},
        ).scalar()
        mavol_rows = db.execute(
            text("select count(*) from mavol_indicators where date = :d and market_type = 'CN'"),
            {"d": d},
        ).scalar()
        mavol20_valid = db.execute(
            text(
                "select count(*) from mavol_indicators "
                "where date = :d and market_type = 'CN' and mavol20 is not null and mavol20 > 0"
            ),
            {"d": d},
        ).scalar()
        pvfrs_rows = db.execute(
            text(
                "select count(*) from mean_frequency_resonance_indicators where date = :d and market_type = 'CN'"
            ),
            {"d": d},
        ).scalar()
        print("date =", d)
        print("distinct codes on date =", distinct_codes)
        print("mavol_indicators rows on date =", mavol_rows)
        print("mavol_indicators mavol20>0 rows on date =", mavol20_valid)
        print("mean_frequency_resonance_indicators rows on date =", pvfrs_rows)
    finally:
        db.close()


if __name__ == "__main__":
    main()

