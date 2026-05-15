# 企业微信配置类
import os
import re
from typing import Optional


def normalize_wechat_app_profile(raw: Optional[str]) -> Optional[str]:
    """
    将用户输入规范为环境变量后缀：仅 A-Z、0-9、下划线，最长 32。
    空或无效则返回 None（表示使用默认 WECHAT_CORP_ID 等）。
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip().upper()
    if not s:
        return None
    cleaned = re.sub(r"[^A-Z0-9_]", "", s)
    if not cleaned:
        return None
    return cleaned[:32]


class WeChatConfig:
    """企业微信配置：默认读 WECHAT_*；指定 app_profile 时读 WECHAT_<PROFILE>_*。"""

    def __init__(self, app_profile: Optional[str] = None):
        self.app_profile = normalize_wechat_app_profile(app_profile)
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None

        if not self.app_profile:
            self.corp_id = os.getenv("WECHAT_CORP_ID")
            self.corp_secret = os.getenv("WECHAT_CORP_SECRET")
            self.agent_id = os.getenv("WECHAT_AGENT_ID")
        else:
            prefix = f"WECHAT_{self.app_profile}_"
            self.corp_id = os.getenv(f"{prefix}CORP_ID")
            self.corp_secret = os.getenv(f"{prefix}CORP_SECRET")
            self.agent_id = os.getenv(f"{prefix}AGENT_ID")

    def is_configured(self) -> bool:
        return bool(
            self.corp_id and str(self.corp_id).strip()
            and self.corp_secret and str(self.corp_secret).strip()
            and self.agent_id and str(self.agent_id).strip()
        )

    def get_access_token(self) -> str:
        """获取企业微信访问令牌"""
        import requests
        import time

        if self.access_token and self.token_expires_at and time.time() < self.token_expires_at:
            return self.access_token

        if not self.is_configured():
            prof = self.app_profile or "default"
            raise Exception(
                f"企业微信凭证不完整（profile={prof}）。默认需 WECHAT_CORP_ID/WECHAT_CORP_SECRET/WECHAT_AGENT_ID；"
                f"命名 profile 需 WECHAT_{prof}_CORP_ID 等。"
            )

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.corp_secret,
        }

        response = requests.get(url, params=params)
        data = response.json()

        if data.get("errcode") == 0:
            self.access_token = data["access_token"]
            self.token_expires_at = time.time() + data["expires_in"] - 60
            return self.access_token
        raise Exception(f"获取企业微信访问令牌失败: {data}")
