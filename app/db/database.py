from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings
# from models import Base # Ensure your models are imported globally to register them with Base

# 1. Database Engine Setup
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=True, # Set to False in production
)

# 2. Base for Declarative Models
class Base(DeclarativeBase):
    """Base class which provides automated table name
       and supports the geospatial data type."""
    pass

# 3. Asynchronous Session Local
AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 4. Dependency for API endpoints to get a DB session
async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session

# 5. Initialization (for startup event)

async def init_db_and_session(create_tables: bool = False):
    """Initializes the database connection and optionally creates tables."""
    if create_tables:
        async with engine.begin() as conn:
            # Drop and Create ALL tables (DANGER in production, but necessary without Alembic)
            # In a real setup, you'd use checkfirst=True cautiously.
            await conn.run_sync(Base.metadata.create_all)
            print("Database tables created.")
