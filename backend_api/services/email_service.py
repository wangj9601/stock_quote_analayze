"""
邮件推送服务
提供邮件发送功能，支持HTML格式正文和CSV附件
"""

import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """SMTP配置"""
    host: str  # SMTP服务器地址
    port: int  # SMTP端口
    username: str  # 发件人账号
    password: str  # 发件人密码
    use_tls: bool  # 是否使用TLS
    from_email: str  # 发件人邮箱
    from_name: str  # 发件人名称


@dataclass
class EmailSendResult:
    """邮件发送结果"""
    success: bool
    message: str = ""
    error: Optional[str] = None


class EmailSendException(Exception):
    """邮件发送异常"""
    pass


class EmailService:
    """邮件推送服务"""
    
    def __init__(self, smtp_config: SMTPConfig):
        """
        初始化邮件服务
        
        Args:
            smtp_config: SMTP配置对象
        """
        self.config = smtp_config
        logger.info(f"邮件服务初始化完成: {smtp_config.host}:{smtp_config.port}")
    
    def send_report_email(
        self, 
        to_email: str, 
        subject: str, 
        content: str, 
        attachment_path: str
    ) -> EmailSendResult:
        """
        发送报告邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件正文(HTML格式)
            attachment_path: CSV附件路径
            
        Returns:
            EmailSendResult: 发送结果
            
        Raises:
            EmailSendException: 发送失败时抛出
        """
        try:
            # 验证邮箱地址
            if not self.validate_email(to_email):
                error_msg = f"无效的邮箱地址: {to_email}"
                logger.error(error_msg)
                raise EmailSendException(error_msg)
            
            # 验证附件文件存在
            attachment_file = Path(attachment_path)
            if not attachment_file.exists():
                error_msg = f"附件文件不存在: {attachment_path}"
                logger.error(error_msg)
                raise EmailSendException(error_msg)
            
            # 创建邮件对象
            msg = MIMEMultipart()
            msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # 添加HTML正文
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 添加CSV附件
            with open(attachment_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype='csv')
                attachment.add_header(
                    'Content-Disposition', 
                    'attachment', 
                    filename=attachment_file.name
                )
                msg.attach(attachment)
            
            # 连接SMTP服务器并发送
            logger.info(f"正在连接SMTP服务器: {self.config.host}:{self.config.port}")
            
            if self.config.use_tls:
                # 使用TLS加密连接
                with smtplib.SMTP(self.config.host, self.config.port, timeout=30) as server:
                    server.starttls()
                    server.login(self.config.username, self.config.password)
                    server.send_message(msg)
            else:
                # 使用SSL加密连接或不加密
                if self.config.port == 465:
                    # SSL连接
                    with smtplib.SMTP_SSL(self.config.host, self.config.port, timeout=30) as server:
                        server.login(self.config.username, self.config.password)
                        server.send_message(msg)
                else:
                    # 不加密连接
                    with smtplib.SMTP(self.config.host, self.config.port, timeout=30) as server:
                        server.login(self.config.username, self.config.password)
                        server.send_message(msg)
            
            success_msg = f"邮件发送成功: {to_email}"
            logger.info(success_msg)
            return EmailSendResult(success=True, message=success_msg)
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP认证失败: {str(e)}"
            logger.error(error_msg)
            raise EmailSendException(error_msg)
        
        except smtplib.SMTPConnectError as e:
            error_msg = f"SMTP连接失败: {str(e)}"
            logger.error(error_msg)
            raise EmailSendException(error_msg)
        
        except smtplib.SMTPException as e:
            error_msg = f"SMTP错误: {str(e)}"
            logger.error(error_msg)
            raise EmailSendException(error_msg)
        
        except Exception as e:
            error_msg = f"邮件发送失败: {str(e)}"
            logger.error(error_msg)
            raise EmailSendException(error_msg)
    
    def validate_email(self, email: str) -> bool:
        """
        验证邮箱地址格式
        
        Args:
            email: 邮箱地址
            
        Returns:
            bool: 是否有效
        """
        if not email or not isinstance(email, str):
            return False
        
        # 邮箱格式正则表达式
        # 支持常见的邮箱格式，如: user@example.com, user.name@example.co.uk
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        return bool(re.match(email_pattern, email.strip()))
