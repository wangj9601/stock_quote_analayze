"""
请求日志中间件
"""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"API请求 - "
                f"方法: {request.method}, "
                f"路径: {request.url.path}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}, "
                f"状态码: {response.status_code}, "
                f"处理时间: {process_time:.3f}秒"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            error_detail = f"请求处理发生错误: {str(e)}"
            logger.error(
                f"{error_detail} - "
                f"方法: {request.method}, "
                f"路径: {request.url.path}, "
                f"IP: {client_host}, "
                f"User-Agent: {user_agent}, "
                f"处理时间: {process_time:.3f}秒"
            )
            raise
