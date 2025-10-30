from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_db
from db import models
from db import schemas
from core import security
from sqlalchemy import select, or_

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from core.security import verify_password, create_access_token
from db.models import TruckMovementStatus # Import the enum

import logging

router = APIRouter(tags=["Auth & Users"])
logger = logging.getLogger(__name__)

@router.post("/register/customer",status_code=status.HTTP_201_CREATED)
async def register_customer(
    user_in: schemas.UserCreate,
    db: AsyncSession = Depends(get_async_db)
):
    
    print(user_in)
    
    # Check if a user with the same email or phone number already exists
    stmt = select(models.User).where(
        or_(
            models.User.email == user_in.email,
            models.User.phone_number == user_in.phone_number
        )
    )
    existing_user = (await db.execute(stmt)).scalars().first()

    if existing_user:
        logger.info(f"Registration attempt failed: user already exists (email={existing_user.email})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email or phone number already exists."
        )

    # Hash the password and create the new user
    hashed_password = security.get_password_hash(user_in.password)
    new_user = models.User(
        email=user_in.email,
        phone_number=user_in.phone_number,
        hashed_password=hashed_password,
        role=models.UserRole.customer  # Default to customer role
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"New customer registered successfully: user_id={new_user.id}, email={new_user.email}")

    access_token = create_access_token(
        data={"sub": new_user.email, "user_id": new_user.id, "role": new_user.role.value}
    )

    response = {}

    response.update({"access_token": access_token})
    response.update({"email":new_user.email})
    
    print(response)

    return response


# --- Registration Endpoints ---

@router.post("/register/truck", response_model=schemas.Token)
async def register_truck_owner(
    owner_in: schemas.TruckOwnerCreate, 
    db: AsyncSession = Depends(get_async_db)
):
    # 1. Check if user/email exists
    existing_user_stmt = select(models.User).where(
        or_(
            models.User.phone_number == owner_in.phone_number,
            models.User.email == owner_in.email
        )
    )
    
    existing_user = (await db.execute(existing_user_stmt)).scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exsists."
        )

    # 2. Hash password and create User (Role: Truck)
    hashed_password = security.get_password_hash(owner_in.password)
    db_user = models.User(
        email=owner_in.email,
        hashed_password=hashed_password,
        phone_number=owner_in.phone_number,
        role=models.UserRole.truck 
    )
    db.add(db_user)
    await db.flush() # Flush to get the user ID for the truck table

    # 3. Create the corresponding Truck entry
    db_truck = models.Truck(
        owner_user_id=db_user.id,
        name=owner_in.truck_name,
        is_active=False,
        movement_status=TruckMovementStatus.serving # Default to stable
    )
    db.add(db_truck)
    
    await db.commit()
    await db.refresh(db_user)

    # 4. Generate and return JWT token
    access_token = create_access_token(
        data={"sub": db_user.email, "user_id": db_user.id, "role": db_user.role.value}
    )
    return schemas.Token(access_token=access_token)

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_async_db)
):
    # Fetching user by email (OAuth2 form uses 'username' as the email field)
    stmt = select(models.User).where(models.User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    # Validate user existence and password
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Failed login attempt for user: %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT access token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role.value
        }
    )

    return schemas.Token(access_token=access_token)
