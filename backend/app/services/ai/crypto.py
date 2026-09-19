"""API Key 的静态加密。

为什么需要
----------
密钥存在服务器 SQLite 里。数据库文件本身可能被备份、复制、误传到别处 ——
明文存储意味着**文件泄漏 = 密钥泄漏**。这里做一层静态加密：
即使拿到 ``smoking.db`` 也解不出密钥。

密钥来源
--------
用部署时配置的 ``AI_ADMIN_TOKEN`` 经 PBKDF2 派生（配一个固定的应用盐）。
因此：

* 令牌与数据库**分开保管**（令牌在 api.env，库在 data/），拿到其中一个不够；
* 未配置 ``AI_ADMIN_TOKEN`` 时不加密，但那种部署下写接口本来就只允许本机访问。

轮换行为
--------
换了 ``AI_ADMIN_TOKEN`` 后旧密文解不开 —— 此时按「密钥未配置」处理，
需要重新填写。这是安全的一侧失败（fail-safe），不会退回明文。

实现
----
只用标准库：``hashlib.pbkdf2_hmac`` 派生密钥，``hmac`` + ``sha256`` 做
密钥流（CTR 模式），再 ``hmac.compare_digest`` 校验完整性。
不引入 cryptography 依赖 —— 本模块只保护一个短字符串，
用不上通用加密库的能力。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

#: 密文前缀，用于识别「已加密」与「历史明文」两种存量形态
ENCRYPTED_PREFIX = "enc:v1:"

#: 应用级盐（固定值即可 —— 它的作用是把派生绑定到本应用，
#: 真正的机密性来自 AI_ADMIN_TOKEN 本身）
_APP_SALT = b"smoking-monitoring.ai-model-settings.v1"

#: PBKDF2 迭代次数
_ITERATIONS = 120_000

_KEY_LEN = 32
_NONCE_LEN = 16


def _derive(secret: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), _APP_SALT, _ITERATIONS, _KEY_LEN)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """用 HMAC-SHA256 生成密钥流（CTR 模式，单块足够）。"""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, stream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, stream))


def is_encrypted(value: str) -> bool:
    return value.startswith(ENCRYPTED_PREFIX)


def encrypt_api_key(plain: str, secret: str) -> str:
    """加密 API Key。

    ``secret`` 为空（未配置管理员令牌）时原样返回 —— 由调用方决定是否告警。
    """
    if not plain:
        return ""
    if not secret:
        return plain

    key = _derive(secret)
    nonce = os.urandom(_NONCE_LEN)
    body = plain.encode("utf-8")
    cipher = _xor(body, _keystream(key, nonce, len(body)))
    # 完整性校验：防止密文被篡改后静默解出错误内容
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    packed = nonce + tag + cipher
    return ENCRYPTED_PREFIX + base64.urlsafe_b64encode(packed).decode("ascii")


def decrypt_api_key(stored: str, secret: str) -> str:
    """解密 API Key。

    解不开时返回空串（按「未配置」处理）并记一条**不含密文与密钥**的日志。
    换令牌后需要重新填写 —— fail-safe，不回退明文。
    """
    if not stored:
        return ""
    if not is_encrypted(stored):
        # 历史明文存量：仍可用，但记一条提醒（不含内容）
        logger.warning("AI API Key 以明文存量存在，建议重新保存以启用加密")
        return stored
    if not secret:
        logger.warning("AI API Key 已加密但未配置 AI_ADMIN_TOKEN，无法解密")
        return ""

    try:
        packed = base64.urlsafe_b64decode(stored[len(ENCRYPTED_PREFIX) :].encode("ascii"))
    except (ValueError, TypeError):
        logger.warning("AI API Key 密文格式异常，已按未配置处理")
        return ""

    if len(packed) <= _NONCE_LEN + 16:
        logger.warning("AI API Key 密文长度异常，已按未配置处理")
        return ""

    nonce = packed[:_NONCE_LEN]
    tag = packed[_NONCE_LEN : _NONCE_LEN + 16]
    cipher = packed[_NONCE_LEN + 16 :]

    key = _derive(secret)
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        # 令牌被换过，或密文被改动 —— 两种情况都只能重填
        logger.warning("AI API Key 解密校验失败（可能更换了 AI_ADMIN_TOKEN），需重新填写")
        return ""

    try:
        return _xor(cipher, _keystream(key, nonce, len(cipher))).decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("AI API Key 解密结果异常，已按未配置处理")
        return ""
