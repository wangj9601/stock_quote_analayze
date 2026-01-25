#!/usr/bin/env python3
import requests

r = requests.get('http://localhost:5000/api/admin/pvfrs/backtest/trades/pvfrs_bt_d094fda8_231033')
print('Status:', r.status_code)
print('Response:', r.json())
