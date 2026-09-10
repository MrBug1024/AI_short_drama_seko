"""鉴权工具：密码哈希 + JWT 签发与校验"""
import hashlib
import hmac
import base64
import json
import time
import secrets
from typing import Optional, Dict, Any

from app.core.config import settings


# ============== 密码哈希（PBKDF2-SHA256，无第三方依赖）==============

_HASH_ITERATIONS = 200_000
_HASH_ALGO = "sha256"


def hash_password(password: str) -> str:
    """生成密码哈希：pbkdf2$<salt_b64>$<hash_b64>"""
    if not password:
        raise ValueError("密码不能为空")
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"pbkdf2${_HASH_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码"""
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2":
            return False
        iters_i = int(iters)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode("utf-8"), salt, iters_i)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ============== JWT（HS256，无第三方依赖）==============


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode())


def create_access_token(*, user_id: int, role: str = "user", extra: Optional[Dict[str, Any]] = None) -> str:
    """签发 JWT（HS256）"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + settings.JWT_EXPIRE_MINUTES * 60,
    }
    if extra:
        payload.update(extra)
    h = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    signing = f"{h}.{p}".encode()
    sig = hmac.new(settings.JWT_SECRET.encode(), signing, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def decode_token(token: str) -> Dict[str, Any]:
    """解析 JWT；过期/签名错误抛 ValueError"""
    try:
        h, p, s = token.split(".", 2)
    except ValueError:
        raise ValueError("Token 格式错误")
    expected_sig = hmac.new(settings.JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_decode(s), expected_sig):
        raise ValueError("Token 签名错误")
    payload = json.loads(_b64url_decode(p))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token 已过期")
    return payload