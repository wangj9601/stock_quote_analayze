from backend_api.main import app
for route in app.routes:
    if hasattr(route, "path"):
        print(f"{list(route.methods) if hasattr(route, 'methods') else 'N/A'} {route.path}")
