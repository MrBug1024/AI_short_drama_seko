"""AI Provider 管理 API"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.ai.gateway import ai_gateway
from app.models.ai_provider import AIProvider
from app.schemas.task import AIProviderCreate, AIProviderUpdate, AIProviderOut

router = APIRouter()


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


async def _to_out(p: AIProvider) -> AIProviderOut:
    out = AIProviderOut.model_validate(p)
    out.api_key_masked = mask_key(p.api_key)
    return out


@router.get("/ai-providers", response_model=List[AIProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIProvider).order_by(desc(AIProvider.priority)))
    providers = result.scalars().all()
    return [await _to_out(p) for p in providers]


@router.post("/ai-providers", response_model=AIProviderOut)
async def create_provider(data: AIProviderCreate, db: AsyncSession = Depends(get_db)):
    p = AIProvider(**data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return await _to_out(p)


@router.patch("/ai-providers/{pid}", response_model=AIProviderOut)
async def update_provider(pid: int, data: AIProviderUpdate, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(AIProvider).where(AIProvider.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "服务商不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return await _to_out(p)


@router.delete("/ai-providers/{pid}")
async def delete_provider(pid: int, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(AIProvider).where(AIProvider.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "服务商不存在")
    if p.is_builtin:
        raise HTTPException(400, "内置服务商不可删除")
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.post("/ai-providers/{pid}/test")
async def test_provider(pid: int, db: AsyncSession = Depends(get_db)):
    """测试 Provider 连通性"""
    p = (await db.execute(select(AIProvider).where(AIProvider.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "服务商不存在")

    if not p.api_key or not p.base_url:
        raise HTTPException(400, "API Key 或 Base URL 未配置")

    import aiohttp
    try:
        url = f"{p.base_url.rstrip('/')}/chat/completions"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(
                url,
                json={
                    "model": p.text_model or "default",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
                headers={
                    "Authorization": f"Bearer {p.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                ok = resp.status in (200, 429)  # 429 也算通（配额限制）
                msg = ""
                if resp.status == 429:
                    msg = "连通成功，但配额受限"
                elif resp.status == 200:
                    msg = "连通成功"
                else:
                    txt = await resp.text()
                    msg = f"状态码 {resp.status}: {txt[:100]}"

                p.last_test_at = datetime.utcnow()
                p.last_test_status = "ok" if ok else "failed"
                await db.commit()
                return {"ok": ok, "msg": msg, "status": resp.status}
    except Exception as e:
        p.last_test_at = datetime.utcnow()
        p.last_test_status = "failed"
        await db.commit()
        return {"ok": False, "msg": str(e)}