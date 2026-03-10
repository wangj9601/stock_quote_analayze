"""
简单企业微信发送消息测试程序。

使用方式：
1. 在 .env 或系统环境变量中正确配置：
   - WECHAT_CORP_ID
   - WECHAT_CORP_SECRET
   - WECHAT_AGENT_ID
   （注意：这些变量需与企业微信后台应用配置一致）

2. 可通过命令行参数指定接收人和内容：
   python -m pytest test/test_wechat_send_message.py -q  # 若仅查看代码不建议执行，会真实发送
   python test/test_wechat_send_message.py zhangsan "测试消息"

   或设置环境变量：
   - WECHAT_TEST_USER_IDS  例如： "zhangsan,lisi"
   - WECHAT_TEST_CONTENT   例如： "这是一条来自测试程序的企业微信消息"

   然后执行：
   python test/test_wechat_send_message.py
"""

from typing import List
import os
import sys
from pathlib import Path

# 确保可以从项目根目录导入 backend_core 等包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载项目根目录的 .env，否则 os.getenv() 读不到配置
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from backend_core.wechat.wechat_service import WeChatService


def _get_target_users_from_args_or_env() -> List[str]:
    """从命令行参数或环境变量获取目标企业微信账号列表"""
    # 命令行第一个参数：逗号分隔的用户ID列表
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        raw = sys.argv[1].strip()
        return [u.strip() for u in raw.split(",") if u.strip()]

    # 环境变量 WECHAT_TEST_USER_IDS：逗号分隔
    raw = os.getenv("WECHAT_TEST_USER_IDS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]

    return []


def _get_content_from_args_or_env() -> str:
    """从命令行参数或环境变量获取发送内容"""
    if len(sys.argv) >= 3 and sys.argv[2].strip():
        return sys.argv[2].strip()

    env_content = os.getenv("WECHAT_TEST_CONTENT")
    if env_content and env_content.strip():
        return env_content.strip()

    return "这是一条来自股票分析系统测试程序的企业微信消息。"


def main() -> None:
    """通过企业微信向同事发送一条测试消息"""
    # 检查基础配置是否完整
    # WeChatService 内部会使用 WeChatConfig 读取
    corp_id = os.getenv("WECHAT_CORP_ID")
    corp_secret = os.getenv("WECHAT_CORP_SECRET")
    agent_id = os.getenv("WECHAT_AGENT_ID")

    if not corp_id or not corp_secret or not agent_id:
        print("企业微信配置不完整，请在环境变量或 .env 中设置：")
        print("  WECHAT_CORP_ID")
        print("  WECHAT_CORP_SECRET")
        print("  WECHAT_AGENT_ID")
        sys.exit(1)

    users = _get_target_users_from_args_or_env()
    if not users:
        print("未指定接收人。请至少通过以下一种方式指定：")
        print("  1) 命令行参数：python test/test_wechat_send_message.py zhangsan")
        print("     或多个接收人：python test/test_wechat_send_message.py zhangsan,lisi")
        print("  2) 环境变量 WECHAT_TEST_USER_IDS=zhangsan,lisi")
        sys.exit(1)

    content = _get_content_from_args_or_env()

    print(f"准备向以下企业微信账号发送消息：{users}")
    print(f"消息内容：{content}")

    service = WeChatService()
    try:
        ok = service.send_text_message(users, content)
    except Exception as e:
        print(f"发送过程中出现异常：{e}")
        sys.exit(1)

    if ok:
        print("企业微信消息发送成功。")
        sys.exit(0)
    else:
        print("企业微信消息发送失败，请检查企业微信配置和用户ID是否正确。")
        sys.exit(1)


if __name__ == "__main__":
    main()

