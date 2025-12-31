
from backend_api.database import SessionLocal
from backend_api.models import MAIndicators, MACDIndicators, KDJIndicators, RSIIndicators, BOLLIndicators, MAVOLIndicators, MeanFrequencyResonanceIndicators
from sqlalchemy import text

db = SessionLocal()

def check_table(model, name):
    try:
        item = db.query(model).first()
        if item:
            print(f"{name}: market_type='{item.market_type}'")
        else:
            print(f"{name}: Empty")
    except Exception as e:
        print(f"{name}: Error - {e}")

check_table(MAIndicators, "MA")
check_table(MACDIndicators, "MACD")
check_table(KDJIndicators, "KDJ")
check_table(RSIIndicators, "RSI")
check_table(BOLLIndicators, "BOLL")
check_table(MAVOLIndicators, "MAVOL")
check_table(MeanFrequencyResonanceIndicators, "PVFRS")

db.close()
