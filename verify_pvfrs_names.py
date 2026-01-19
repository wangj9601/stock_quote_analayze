
import requests
import json

def test_pvfrs_names():
    url = "http://127.0.0.1:5000/api/screening/pvfrs-strategy?scope=all"
    
    try:
        print(f"Calling API: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            print(response.text)
            return
            
        result = response.json()
        if not result.get('success'):
            print(f"Error: API returned success=False")
            print(result.get('message'))
            return
            
        data = result.get('data', [])
        print(f"Found {len(data)} stocks.")
        
        # Check first 5 stocks
        for i, stock in enumerate(data[:10]):
            code = stock.get('symbol') or stock.get('code')
            name = stock.get('name')
            print(f"{i+1}. Code: {code}, Name: {name}")
            
            if name and name.startswith('股票'):
                print(f"  [X] FAILED: Name is still default '{name}'")
            elif name:
                print(f"  [V] PASSED: Real name found.")
            else:
                print(f"  [X] FAILED: Name is missing.")
                
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_pvfrs_names()
