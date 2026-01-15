from backend_core.database.db import SessionLocal
from sqlalchemy import text

def check_duplicates():
    session = SessionLocal()
    try:
        sql = """
        SELECT code, date, market_type, count(*) 
        FROM mean_frequency_resonance_indicators 
        WHERE code = '688114' AND date = '2026-01-13'
        GROUP BY code, date, market_type
        """
        result = session.execute(text(sql))
        rows = result.fetchall()
        print("Duplicates for 688114 on 2026-01-13:")
        for row in rows:
            print(f"Code: {row[0]}, Date: {row[1]}, Market Type: {row[2]}, Count: {row[3]}")
            
        sql_all = "SELECT DISTINCT market_type FROM mean_frequency_resonance_indicators"
        result_all = session.execute(text(sql_all))
        print("\nAll distinct market types in table:")
        for row in result_all.fetchall():
            print(f"'{row[0]}'")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_duplicates()
