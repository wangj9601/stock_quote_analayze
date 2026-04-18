import akshare as ak

print("Testing THS...")
try:
    df2 = ak.fund_etf_spot_ths()
    print('THS Columns:', df2.columns.tolist() if df2 is not None else None)
    if df2 is not None and len(df2)>0:
        print(df2[df2['基金代码'] == '510300'].to_dict('records') if '基金代码' in df2.columns else df2.head(1).to_dict('records'))
except Exception as e:
    print('THS FAIL:', e)

print("\nTesting SINA...")
try:
    df3 = ak.fund_etf_category_sina(symbol='ETF基金')
    print('SINA Columns:', df3.columns.tolist() if df3 is not None else None)
    if df3 is not None and len(df3)>0:
        print(df3[df3['代码'] == 'sh510300'].to_dict('records') if '代码' in df3.columns else df3.head(1).to_dict('records'))
except Exception as e:
    print('SINA FAIL:', e)
