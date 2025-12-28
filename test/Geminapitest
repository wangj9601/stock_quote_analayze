import google.generativeai as genai
from google.api_core import exceptions
import os   

# 设置你的代理端口（请根据你代理软件的实际端口修改，常见为 7890 或 1080）
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:9910'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:9910'

# 1. 配置 API 密钥
API_KEY = "AIzaSyBH1CWisGCsTgWiPsCvjbwV60wq8I-DKgQ"
genai.configure(api_key=API_KEY)

def test_gemini_connection():
    try:
        # 2. 初始化模型 (推荐使用最新的 gemini-1.5-flash)
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
        # 3. 发起一个简单的测试请求
        print("正在验证 API 密钥...")
        response = model.generate_content("你好，请确认连接正常。")
        
#“现在是 2025 年 12 月 29 日周一盘前。我是一名稳健型投资者，交易环境为 A 股（T+1 制度）。目前市场处于下跌趋势。

#请帮我分析 [输入股票名称或代码]：

#趋势研判：该股目前是否触及强支撑位？

#风控建议：如果我进场，基于 2%-5% 的浮动止损要求，最科学的离场点位应设在哪里？

#操作纪律：考虑到下跌趋势，如果今日波动不明朗，是否应执行‘空仓观望’策略？

#请给出极其谨慎的建议，宁可错过，不可做错。”
        
#“现在是 2025 年 12 月 29 日周一盘前。我是一名稳健型投资者，交易环境为 A 股（T+1 制度）。目前市场处于下跌趋势。

#请帮我分析 [输入股票名称或代码]：

#趋势研判：该股目前是否触及强支撑位？

#风控建议：如果我进场，基于 2%-5% 的浮动止损要求，最科学的离场点位应设在哪里？

#操作纪律：考虑到下跌趋势，如果今日波动不明朗，是否应执行‘空仓观望’策略？

#请给出极其谨慎的建议，宁可错过，不可做错。”
        
        print("-" * 30)
        print("✅ 验证成功！")
        print(f"AI 回复: {response.text}")
        print("-" * 30)
        
    except exceptions.Unauthenticated:
        print("❌ 错误：API 密钥无效 (400 API_KEY_INVALID)。请检查密钥是否复制正确。")
    except exceptions.PermissionDenied:
        print("❌ 错误：权限被拒绝。请确认该 API 密钥是否已在 Google AI Studio 中启用。")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")

if __name__ == "__main__":
    test_gemini_connection()