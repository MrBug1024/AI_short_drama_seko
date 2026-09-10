"""数据库连接（异步 SQLAlchemy + SQLite）"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


# 异步引擎
# 注意：echo 会打印每条 SQL，严重拖慢写入并加剧 SQLite 锁竞争，强制关闭
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# SQLite 并发优化：WAL 模式允许读写并发，busy_timeout 让写冲突时等待而非直接报 database is locked
if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# 会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库（创建所有表 + 轻量迁移）"""
    # 先 import 所有 model，让 Base 知道
    from app.models import (
        project, episode, script, character, scene,
        prop, shot, canvas, generation_task, ai_provider, skill,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_schema)


def _migrate_schema(sync_conn):
    """轻量迁移：为旧表补充新增列（SQLite ALTER TABLE ADD COLUMN）

    create_all 只建新表，不会给已有表加列。这里手动检查并补列，
    避免用户删库重建。
    """
    from sqlalchemy import text, inspect

    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    # 表名 -> {列名: DDL 类型}
    migrations = {
        "characters": {
            "backstory": "TEXT DEFAULT ''",
            "view_images": "JSON DEFAULT '{}'",
        },
    }

    for table, columns in migrations.items():
        if table not in existing_tables:
            continue
        current_cols = {c["name"] for c in inspector.get_columns(table)}
        for col, ddl in columns.items():
            if col not in current_cols:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))