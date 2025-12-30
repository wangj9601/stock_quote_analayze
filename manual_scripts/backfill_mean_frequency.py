import sys
import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from backend_api.models import Base, HistoricalQuotes, HistoricalQuotesHK, MeanFrequencyResonanceIndicators
from backend_api.database import SessionLocal, engine

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def calculate_and_save_indicators(db, stock_code, market_type, force_update=True):
    """
    Calculate Mean Frequency Resonance Indicators for a stock and save to DB.
    """
    print(f"Processing {stock_code} ({market_type})...")
    
    # 1. Fetch Historical Data
    if market_type == 'CN':
        query = db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.close,
            HistoricalQuotes.volume
        ).filter(HistoricalQuotes.code == stock_code).order_by(HistoricalQuotes.date.asc())
    else:  # HK
        query = db.query(
            HistoricalQuotesHK.date,
            HistoricalQuotesHK.close,
            HistoricalQuotesHK.volume
        ).filter(HistoricalQuotesHK.code == stock_code).order_by(HistoricalQuotesHK.date.asc())
        
    data = pd.read_sql(query.statement, db.bind)
    
    if data.empty:
        print(f"No history found for {stock_code}")
        return

    # Ensure date is string YYYY-MM-DD
    if market_type == 'CN':
        # data['date'] might be python date objects
        data['date'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m-%d')
    else:
        # HK date is already string (TEXT), assuming format is correct or standardizing
        # Usually it is YYYY-MM-DD
        pass
        
    df = data.copy()
    
    # 2. Calculate Indicators
    # Rolling window 20
    window = 20
    
    # MA20 (d)
    df['ma20'] = df['close'].rolling(window=window).mean()
    
    # MAVOL20 (m)
    df['mavol20'] = df['volume'].rolling(window=window).mean()
    
    # Macro Displacement Delta = Close_t - Close_{t-19} (20-day change)
    # Using shift(window - 1) because window=1 means same day. Window=20 means t and t-19.
    df['delta'] = df['close'] - df['close'].shift(window - 1)
    
    # Instant Deviation (d20 - d) = Close - MA20
    df['instant_deviation'] = df['close'] - df['ma20']
    
    # Efficiency (m20 - m) = Volume - MAVOL20
    df['efficiency'] = df['volume'] - df['mavol20']
    
    # Frequency: Z (Rising) and F (Falling) over last 20 days
    # Rising Day: Close > Prev Close
    df['is_rising'] = (df['close'] > df['close'].shift(1)).astype(int)
    # Falling Day: Close < Prev Close
    df['is_falling'] = (df['close'] < df['close'].shift(1)).astype(int)
    
    # Rolling sum for Z and F
    df['z'] = df['is_rising'].rolling(window=window).sum()
    df['f'] = df['is_falling'].rolling(window=window).sum()
    
    # Drop NaNs (first 19 rows)
    df_result = df.dropna().copy()
    
    if df_result.empty:
        print(f"Not enough data for {stock_code}")
        return

    # 3. Save to DB
    # "If date exists, delete then add".
    # Since we are processing the whole stock history, we can delete all for this stock first?
    # Or just delete the dates we have calculated.
    # To be safe and compliant with "batch process", we can check overlap.
    
    # Let's delete existing records for this stock to facilitate clean insert
    # This matches "delete then add" for the dates involved.
    try:
        delete_stmt = text("DELETE FROM mean_frequency_resonance_indicators WHERE code = :code AND market_type = :market_type")
        db.execute(delete_stmt, {"code": stock_code, "market_type": market_type})
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error deleting old data: {e}")
        return

    # Bulk Insert
    # Convert DataFrame to list of dicts
    records = []
    for _, row in df_result.iterrows():
        record = {
            "code": stock_code,
            "date": row['date'],
            "market_type": market_type,
            "macro_displacement_delta": row['delta'],
            "instant_deviation": row['instant_deviation'],
            "rising_days_z": int(row['z']),
            "falling_days_f": int(row['f']),
            "efficiency_m20_minus_m": row['efficiency'],
            "ma20_d": row['ma20'],
            "mavol20_m": row['mavol20'],
            "created_at": datetime.now()
        }
        records.append(record)
    
    # Batch insert to avoid huge packet size if history is long
    batch_size = 1000
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            db.bulk_insert_mappings(MeanFrequencyResonanceIndicators, batch)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error inserting batch {i} for {stock_code}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Backfill Mean Frequency Resonance Indicators')
    parser.add_argument('--market', type=str, choices=['CN', 'HK'], help='Market type: CN or HK')
    parser.add_argument('--code', type=str, help='Stock code to process (if not specified, process all stocks)')
    args = parser.parse_args()
    
    print("Starting Mean Frequency Resonance Indicators Backfill...")
    
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # If both market and code are specified, process only that stock
        if args.market and args.code:
            print(f"Processing single stock: {args.code} ({args.market})...")
            try:
                calculate_and_save_indicators(db, args.code, args.market)
                print(f"Successfully processed {args.code} ({args.market})")
            except Exception as e:
                print(f"Error processing {args.code} ({args.market}): {e}")
            return
        
        # If only market is specified, process all stocks in that market
        if args.market:
            if args.market == 'CN':
                print("Fetching A-Share codes...")
                codes = db.query(HistoricalQuotes.code).distinct().all()
                codes = [c[0] for c in codes]
                print(f"Found {len(codes)} A-Share stocks.")
                market_type = 'CN'
            else:  # HK
                print("Fetching HK-Share codes...")
                codes = db.query(HistoricalQuotesHK.code).distinct().all()
                codes = [c[0] for c in codes]
                print(f"Found {len(codes)} HK-Share stocks.")
                market_type = 'HK'
            
            for i, code in enumerate(codes):
                try:
                    calculate_and_save_indicators(db, code, market_type)
                except Exception as e:
                    print(f"Error processing {code}: {e}")
                
                if (i+1) % 100 == 0:
                    print(f"Processed {i+1}/{len(codes)} {market_type}-Shares")
        else:
            # Process all stocks in both markets
            # A-Shares
            print("Fetching A-Share codes...")
            cn_codes = db.query(HistoricalQuotes.code).distinct().all()
            cn_codes = [c[0] for c in cn_codes]
            print(f"Found {len(cn_codes)} A-Share stocks.")
            
            for i, code in enumerate(cn_codes):
                try:
                    calculate_and_save_indicators(db, code, 'CN')
                except Exception as e:
                    print(f"Error processing {code}: {e}")
                
                if (i+1) % 100 == 0:
                    print(f"Processed {i+1}/{len(cn_codes)} A-Shares")
            
            # HK-Shares
            print("Fetching HK-Share codes...")
            hk_codes = db.query(HistoricalQuotesHK.code).distinct().all()
            hk_codes = [c[0] for c in hk_codes]
            print(f"Found {len(hk_codes)} HK-Share stocks.")
            
            for i, code in enumerate(hk_codes):
                try:
                    calculate_and_save_indicators(db, code, 'HK')
                except Exception as e:
                    print(f"Error processing {code}: {e}")
                    
                if (i+1) % 100 == 0:
                    print(f"Processed {i+1}/{len(hk_codes)} HK-Shares")

    finally:
        db.close()
    
    print("Backfill Complete.")

if __name__ == "__main__":
    main()
