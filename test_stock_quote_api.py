#!/usr/bin/env python3
"""测试股票报价API"""
import requests
import json

def test_stock_quote_api():
    """测试股票报价API是否正常工作"""
    
    print("🔍 测试股票报价API")
    print("="*50)
    
    # 测试几个常见的股票代码
    test_codes = ["000001", "000002", "600000", "601398"]
    
    try:
        # 调用股票报价API
        url = "http://localhost:5000/api/stock/quote"
        print(f"请求URL: {url}")
        print(f"请求体: {{\"codes\": {test_codes}}}")
        
        response = requests.post(
            url, 
            json={"codes": test_codes},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"响应状态: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ API调用成功")
                print(f"响应结构: {list(data.keys())}")
                
                if 'success' in data:
                    print(f"成功标志: {data['success']}")
                    
                    if data.get('success') and 'data' in data:
                        quote_data = data['data']
                        print(f"返回数据数量: {len(quote_data)}")
                        
                        for stock in quote_data:
                            code = stock.get('code', 'N/A')
                            name = stock.get('name', 'N/A')
                            price = stock.get('current_price', 'N/A')
                            change = stock.get('change_amount', 'N/A')
                            percent = stock.get('change_percent', 'N/A')
                            
                            print(f"  📊 {code} ({name}):")
                            print(f"    当前价: {price}")
                            print(f"    涨跌额: {change}")
                            print(f"    涨跌幅: {percent}%")
                            print()
                    else:
                        print(f"❌ 错误信息: {data.get('message', '未知错误')}")
                else:
                    print(f"⚠️ 响应格式异常")
                    print(f"原始响应: {response.text[:500]}...")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"原始响应: {response.text[:500]}...")
                
        elif response.status_code == 404:
            print(f"❌ 404错误: API端点不存在")
        elif response.status_code == 400:
            print(f"❌ 400错误: 请求参数错误")
            try:
                error_data = response.json()
                print(f"错误信息: {error_data.get('message', '未知错误')}")
            except:
                print(f"错误响应: {response.text}")
        else:
            print(f"❌ 其他错误: {response.status_code}")
            print(f"错误响应: {response.text[:500]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
    except Exception as e:
        print(f"❌ 其他异常: {e}")
    
    print(f"\n🔧 诊断建议:")
    print(f"1. 如果看到404错误，说明股票报价路由未正确注册")
    print(f"2. 检查后端服务是否正在运行: http://localhost:5000")
    print(f"3. 查看后端日志确认路由注册情况")
    print(f"4. 确认stock_manage.py文件中的POST /quote端点存在且无语法错误")

if __name__ == "__main__":
    test_stock_quote_api()
