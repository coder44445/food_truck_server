from fastapi import Depends, HTTPException, status
from typing import Annotated

from sqlalchemy import select
from db import schemas, models
from db.database import get_async_db
from jose import jwt, JWTError
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer

# Define OAuth2 scheme for dependency injection across routers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

# Dependency 1: Extract User ID and Role from Token
async def get_token_data(token: Annotated[str, Depends(oauth2_scheme)]) -> schemas.TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        user_role: str = payload.get("role")

        print(user_id,user_role)
        if user_id is None or user_role is None:
            raise credentials_exception
        
        return schemas.TokenData(user_id=user_id, role=user_role)
        
    except JWTError:
        raise credentials_exception

# Dependency 2: Enforce Customer Role
def get_current_customer(token_data: schemas.TokenData = Depends(get_token_data)):
    if token_data.role != models.UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires customer role."
        )
    return token_data.user_id

# Dependency 3: Enforce Truck Owner Role
def get_current_truck_owner(token_data: schemas.TokenData = Depends(get_token_data)):
    if token_data.role != models.UserRole.truck.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires truck owner role."
        )
    return token_data.user_id

# Helper dependency to fetch the Truck object associated with the owner
async def get_owner_truck(
    owner_id: Annotated[int, Depends(get_current_truck_owner)],
    db: AsyncSession = Depends(get_async_db)
) -> models.Truck:
    stmt = select(models.Truck).where(models.Truck.owner_user_id == owner_id)
    truck = (await db.execute(stmt)).scalars().first()
    
    if not truck:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Truck profile not found for this owner."
        )
    return truck