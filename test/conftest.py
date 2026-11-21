# -*- coding: utf-8 -*-
"""测试公共夹具：确保 JWT 配置在导入 backend_api.config 前合法。"""

import os

# 若环境未显式配置，为 pytest 进程提供可导入的密钥（不写入生产）
os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-jwt-secret-key-at-least-32-chars!!",
)
