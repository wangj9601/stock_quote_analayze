# -*- coding: utf-8 -*-
"""出站 HTTP（连生产 env-sync 网关）。

本机部分环境中 httpx/requests 对生产 HTTPS 会触发 WinError 10054，
而标准库 http.client 稳定可用，故这里统一走 http.client。

安全：拒绝私网 / 回环 / 链路本地等地址，降低 SSRF 风险。
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence
from urllib.parse import urlparse


@dataclass
class RemoteResponse:
    status_code: int
    text: str
    content: bytes = b""

    def json(self) -> Any:
        return json.loads(self.text or "null")


_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def assert_url_allowed_for_outbound(url: str) -> None:
    """校验出站 URL：仅 http(s)，且解析后的全部 IP 不得为内网/保留地址。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的 URL scheme: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"无效 URL: {url}")
    # 字面量 IP
    try:
        literal = ipaddress.ip_address(host)
        if _ip_is_blocked(literal):
            raise ValueError(f"禁止访问内网/保留地址: {host}")
        return
    except ValueError as e:
        if "禁止访问" in str(e):
            raise
        # host 不是字面量 IP，继续 DNS 解析
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos: Sequence = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"无法解析主机名: {host}") from e
    if not infos:
        raise ValueError(f"无法解析主机名: {host}")
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _ip_is_blocked(ip):
            raise ValueError(f"禁止访问内网/保留地址: {host} -> {addr}")


def _request(
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    json_body: Any = None,
    timeout: float = 30.0,
    binary: bool = False,
) -> RemoteResponse:
    assert_url_allowed_for_outbound(url)
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"无效 URL: {url}")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    body: Optional[bytes] = None
    hdrs: Dict[str, str] = {k: str(v) for k, v in (headers or {}).items()}
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False, default=str).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
        hdrs["Content-Length"] = str(len(body))

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.scheme == "https":
        ctx = ssl.create_default_context()
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            parsed.hostname, port=port, timeout=timeout, context=ctx
        )
    else:
        conn = http.client.HTTPConnection(parsed.hostname, port=port, timeout=timeout)

    try:
        conn.request(method.upper(), path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        if binary:
            return RemoteResponse(status_code=resp.status, text="", content=raw)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        return RemoteResponse(status_code=resp.status, text=text, content=raw)
    finally:
        conn.close()


def get(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    return _request("GET", url, headers=headers, timeout=timeout)


def get_bytes(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    return _request("GET", url, headers=headers, timeout=timeout, binary=True)


def post(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    json_body: Any = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    return _request("POST", url, headers=headers, json_body=json_body, timeout=timeout)
