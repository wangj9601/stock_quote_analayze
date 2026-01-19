
from backend_api.database import SessionLocal
from backend_api.models import StockBasicInfo, StockBasicInfoHK

def check_names():
    db = SessionLocal()
    try:
        print("Checking A-shares (StockBasicInfo):")
        a_stocks = db.query(StockBasicInfo).limit(5).all()
        for s in a_stocks:
            print(f"Code: {s.code} (Type: {type(s.code)}), Name: {s.name}")
        
        print("\nChecking HK-shares (StockBasicInfoHK):")
        hk_stocks = db.query(StockBasicInfoHK).limit(5).all()
        for s in hk_stocks:
            print(f"Code: {s.code} (Type: {type(s.code)}), Name: {s.name}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_names()
