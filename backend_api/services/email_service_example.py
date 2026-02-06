"""
EmailService 使用示例
演示如何使用邮件服务发送报告
"""

from backend_api.services.email_service import EmailService, SMTPConfig, EmailSendException
from backend_api.config import SMTP_CONFIG


def create_email_service():
    """创建邮件服务实例"""
    smtp_config = SMTPConfig(
        host=SMTP_CONFIG["host"],
        port=SMTP_CONFIG["port"],
        username=SMTP_CONFIG["username"],
        password=SMTP_CONFIG["password"],
        use_tls=SMTP_CONFIG["use_tls"],
        from_email=SMTP_CONFIG["from_email"],
        from_name=SMTP_CONFIG["from_name"]
    )
    
    return EmailService(smtp_config)


def send_daily_report_example():
    """发送每日报告示例"""
    # 创建邮件服务
    email_service = create_email_service()
    
    # 准备邮件内容
    to_email = "user@example.com"
    subject = "每日股票报告 - 2024-01-15"
    
    # HTML格式的邮件正文
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            h1 { color: #333; }
            .info { background-color: #f0f0f0; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>每日股票报告</h1>
        <div class="info">
            <p><strong>报告日期：</strong>2024-01-15</p>
            <p><strong>报告类型：</strong>汇总报告</p>
            <p><strong>股票数量：</strong>10只</p>
        </div>
        <p>您的自选股历史行情数据已生成，请查看附件中的CSV文件。</p>
        <p>祝您投资顺利！</p>
    </body>
    </html>
    """
    
    # CSV附件路径
    attachment_path = "/path/to/report.csv"
    
    try:
        # 发送邮件
        result = email_service.send_report_email(
            to_email=to_email,
            subject=subject,
            content=html_content,
            attachment_path=attachment_path
        )
        
        if result.success:
            print(f"✓ 邮件发送成功: {result.message}")
        else:
            print(f"✗ 邮件发送失败: {result.error}")
            
    except EmailSendException as e:
        print(f"✗ 发送异常: {str(e)}")


def validate_email_example():
    """验证邮箱地址示例"""
    email_service = create_email_service()
    
    test_emails = [
        "valid@example.com",
        "invalid_email",
        "user@domain",
        "user.name@example.co.uk"
    ]
    
    for email in test_emails:
        is_valid = email_service.validate_email(email)
        status = "✓ 有效" if is_valid else "✗ 无效"
        print(f"{status}: {email}")


if __name__ == "__main__":
    print("=== 邮箱验证示例 ===")
    validate_email_example()
    
    print("\n=== 发送报告示例 ===")
    print("注意：需要先配置环境变量中的SMTP设置")
    # send_daily_report_example()  # 取消注释以实际发送
