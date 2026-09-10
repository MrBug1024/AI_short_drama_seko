"""用户注册 / 登录 / 当前用户"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["用户认证"])


# ============== Schemas ==============

class RegisterBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=200, description="邮箱，用作登录账号")
    password: str = Field(..., min_length=6, max_length=64, description="密码，至少 6 位")
    display_name: str = Field("", max_length=64, description="昵称（可选）")


class LoginBody(BaseModel):
    email: str = Field(...)
    password: str = Field(...)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    created_at: Optional[str] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ============== 工具函数 ==============

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name or u.email.split("@")[0],
        role=u.role,
        created_at=u.created_at.isoformat() if u.created_at else None,
    )


# ============== JWT 依赖（可选 / 强制）==============

async def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """可选鉴权：有 token 就解析，没有就返回 None"""
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    try:
        payload = decode_token(token)
    except Exception:
        return None
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user or user.status != "active":
        return None
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """强制鉴权：未登录 401"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ============== 路由 ==============

@router.post("/register", response_model=TokenOut)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    """注册：邮箱 + 密码 + 昵称（可选）。首注册用户自动成为 admin。"""
    email = _normalize_email(body.email)
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    # 首注册用户自动 admin
    total = (await db.execute(select(User))).scalars().first()
    role = "admin" if total is None else "user"

    user = User(
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        role=role,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, user=_to_user_out(user))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    """登录：邮箱 + 密码"""
    email = _normalize_email(body.email)
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, user=_to_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    """获取当前登录用户信息（前端启动时用）"""
    return _to_user_out(current)