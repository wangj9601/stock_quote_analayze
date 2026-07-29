# -*- coding: utf-8 -*-
"""出站 HTTP（连生产 env-sync 网关）。

本机部分环境中 httpx/requests 对生产 HTTPS 会触发 WinError 10054，
而标准库 http.client 稳定可用，故这里统一走 http.client。
"""

from __future__ import annotations

import http.client
import json
import ssl
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse


@dataclass
class RemoteResponse:
    status_code: int
    text: str

    def json(self) -> Any:
        return json.loads(self.text or "null")


def _request(
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    json_body: Any = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的 URL scheme: {parsed.scheme}")
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
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        return RemoteResponse(status_code=resp.status, text=text)
    finally:
        conn.close()


def get(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    return _request("GET", url, headers=headers, timeout=timeout)


def post(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    json_body: Any = None,
    timeout: float = 30.0,
) -> RemoteResponse:
    return _request("POST", url, headers=headers, json_body=json_body, timeout=timeout)
