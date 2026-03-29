try:
    from backend_api.stock.data_collection_api import router
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
