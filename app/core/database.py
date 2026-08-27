"""Database engine and session management."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

_database_url = settings.async_database_url
if "postgresql" in _database_url and "sqlite" not in _database_url:
    try:
        import psycopg2
    except ImportError:
        _database_url = "sqlite+aiosqlite:///./ai_recommendable.db"

engine = create_async_engine(_database_url, echo=settings.debug, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
