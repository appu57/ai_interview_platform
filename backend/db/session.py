import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, declarative_base

from backend.core.security import get_settings

def get_database_url() -> str:
    """Database url from env file"""
    settings = get_settings()
    db_url = settings.database_url or os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
_engine = None
_session_factory = None

def get_engine():
    global _engine  #Database engines are expensive. Hence create only once and other methods of this code refers to global _engine
    if _engine is None:
        db_url = get_database_url()
        _engine = create_async_engine(  #Because FastAPI is async, queries block threads, using async and await release control back to event loop.
            db_url,
            echo=True
            # connect_args=connect_args,
            # pool_size=settings.db_pool_size,
            # max_overflow=settings.db_max_overflow,
            # pool_timeout=settings.db_pool_timeout_seconds,
            # pool_recycle=settings.db_pool_recycle_seconds,
            # pool_pre_ping=True,
        )
    return _engine

def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            class_= AsyncSession,
            expire_on_commit= False,
            autoflush=False,
            autocommit=False,
            bind = get_engine()
        )
    return _session_factory

# class Base(DeclarativeBase):
#     """Base class for SQLAlchemy models"""

Base = declarative_base()

async def get_db()-> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

@asynccontextmanager
async def get_db_context()-> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise  

# async def init_db() -> None: #Creates a circular dependency with User(Base) because both class imports one another
#     engine = get_engine()
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

async def close_db()->None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

# async def add_mock_data() -> None: # circular dependency  
#     factory = get_session_factory()
#     async with factory() as session:
#         # Check if they exist first
#         from sqlalchemy.future import select
#         result = await session.execute(select(User).where(User.email == "test@mock.ai"))
#         if not result.scalars().first():
#             seed_user = User(
#                 email="test@mock.ai",
#                 hashed_password="hashed_bcrypt_string_here",
#                 full_name="Apoorv S."
#             )
#             session.add(seed_user)
#             await session.commit()
#             print("Success: Test user 'test@mock.ai' saved!")