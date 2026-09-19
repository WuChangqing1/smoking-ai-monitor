"""写接口的管理员令牌保护。

为什么需要
----------
两个站点都有公网入口。模型配置的写接口如果完全匿名开放，
任何访问网页的人都能改 Base URL、换 API Key、测试任意地址、
甚至把平台当成免费的模型代理来消耗 Token —— 必须挡住。

规则
----
1. 配置了 ``AI_ADMIN_TOKEN`` 时：写接口必须带 ``X-AI-Admin-Token``
   且与配置一致（定长比较，避免时序侧信道）。
2. **未配置** ``AI_ADMIN_TOKEN`` 时：
   * 请求来自回环地址（本地开发）→ 放行；
   * 来自公网 → **拒绝**。
   默认拒绝而不是默认开放 —— 不能为了本地方便牺牲线上安全。

令牌本身不写日志、不进错误信息、不下发前端。
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import secrets

from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

#: 管理员令牌请求头
ADMIN_TOKEN_HEADER = "X-AI-Admin-Token"

#: 回环来源判定
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def get_admin_token() -> str:
    """读取配置的管理员令牌（每次读取，便于测试注入）。"""
    return (settings.ai_admin_token or "").strip()


def is_loopback(request: Request) -> bool:
    """判断请求是否来自本机。"""
    client = request.client
    if client is None:
        return False
    host = (client.host or "").strip()
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_admin(request: Request) -> None:
    """写接口前置校验。不通过时抛 401 / 403。

    * 401 —— 需要令牌但没提供，或提供的不对
    * 403 —— 未配置令牌且来自公网（明确告知未开放）
    """
    expected = get_admin_token()
    provided = (request.headers.get(ADMIN_TOKEN_HEADER) or "").strip()

    if expected:
        # 定长比较，避免通过响应时间推测令牌
        if provided and hmac.compare_digest(provided, expected):
            return
        # 令牌已配置但请求没带或不对
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员令牌",
            headers={"X-Need-Admin-Token": "1"},
        )

    # 未配置令牌：仅允许本机
    if is_loopback(request):
        return

    logger.warning(
        "拒绝来自非本机的 AI 配置写请求：client=%s path=%s（未配置 AI_ADMIN_TOKEN）",
        request.client.host if request.client else "unknown",
        request.url.path,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="该配置接口未对外开放",
    )


def generate_token() -> str:
    """生成一个高强度令牌，供部署时使用。"""
    return secrets.token_urlsafe(32)
