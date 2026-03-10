# 企业微信服务
import requests
import json
from typing import List, Dict, Any, Optional
from .wechat_config import WeChatConfig

class WeChatService:
    """企业微信服务"""
    
    def __init__(self):
        self.config = WeChatConfig()
    
    def send_text_message(self, user_ids: List[str], content: str) -> bool:
        """发送文本消息"""
        access_token = self.config.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        
        data = {
            "touser": "|".join(user_ids),
            "msgtype": "text",
            "agentid": self.config.agent_id,
            "text": {
                "content": content
            }
        }
        
        response = requests.post(url, json=data)
        result = response.json()

        # 调试输出，方便定位发送失败原因（如用户不在应用可见范围、userid 不存在等）
        if result.get('errcode') != 0:
            print(f"企业微信发送文本消息失败: {result}")
        
        return result.get('errcode') == 0
    
    def send_file_message(self, user_ids: List[str], file_path: str, file_name: str) -> bool:
        """发送文件消息"""
        # 1. 上传文件获取media_id
        media_id = self._upload_file(file_path)
        if not media_id:
            return False
        
        # 2. 发送文件消息
        access_token = self.config.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        
        data = {
            "touser": "|".join(user_ids),
            "msgtype": "file",
            "agentid": self.config.agent_id,
            "file": {
                "media_id": media_id
            }
        }
        
        response = requests.post(url, json=data)
        result = response.json()
        
        return result.get('errcode') == 0
    
    def _upload_file(self, file_path: str) -> Optional[str]:
        """上传文件获取media_id"""
        access_token = self.config.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=file"
        
        with open(file_path, 'rb') as f:
            files = {'media': f}
            response = requests.post(url, files=files)
        
        result = response.json()
        if result.get('errcode') == 0:
            return result['media_id']
        else:
            print(f"文件上传失败: {result}")
            return None
