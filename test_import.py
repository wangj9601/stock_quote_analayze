import traceback
try:
    import backend_api.admin.trading_calendar
except Exception as e:
    traceback.print_exc()
