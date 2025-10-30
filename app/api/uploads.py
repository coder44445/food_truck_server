from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi import Form
from api.dependencies import get_current_truck_owner
from db.database import get_async_db
from db import models
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
import os
import uuid
import datetime
import shutil
import json
from sqlalchemy import select, update

# --- Configuration (Must match app/main.py) ---
STORAGE_DIR = "uploaded_files"
PUBLIC_BASE_URL = "/static/" 
LOCAL_UPLOAD_FOLDER = os.path.join(os.getcwd(), STORAGE_DIR)
os.makedirs(LOCAL_UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(tags=["File Uploads"])

async def update_image_url(
    db: AsyncSession, 
    truck_id: int, 
    url: str, 
    target: str # 'profile' or 'food'
) -> None:
    """Updates the truck's profile_image_url or appends to food_images_urls."""
    
    truck = await db.get(models.Truck, truck_id)
    if truck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Truck not found.")
    
    if target == 'profile':
        # Overwrite the single profile image URL
        truck.profile_image_url = url
    elif target == 'food':
        # Append the new URL to the list of food images
        # Ensure it is initialized if null
        current_urls = truck.food_images_urls or []
        
        # Check if the URL is already present before appending (optional)
        if url not in current_urls:
            current_urls.append(url)
            truck.food_images_urls = current_urls
        
    await db.commit()


@router.post("/upload/image")
async def upload_image(
    owner_id: Annotated[int, Depends(get_current_truck_owner)],
    file: Annotated[UploadFile, File()],
    # NEW: Form data to specify where the URL should be saved
    target: Annotated[str, Form(description="Target field: 'profile' or 'food'")], 
    db: Annotated[AsyncSession, Depends(get_async_db)],
):
    """
    Handles file upload, saves the file locally, and saves the resulting URL 
    to the truck's database record (either profile or food images).
    """
    
    # 1. Validation
    if target not in ['profile', 'food']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target must be 'profile' or 'food'.")

    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}."
        )
        
    MAX_FILE_SIZE_MB = 5
    file_size_check = await file.read(MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
    await file.seek(0)
    if len(file_size_check) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the {MAX_FILE_SIZE_MB}MB limit."
        )

    # 2. Secure File Naming
    file_extension = os.path.splitext(file.filename)[1]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    unique_filename = f"truck_{owner_id}_{timestamp}_{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(LOCAL_UPLOAD_FOLDER, unique_filename)

    # 3. Save File (Local Storage)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        print(f"File write error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save file on the server.")
    finally:
        await file.close()

    # 4. Generate URL and Save to Database (CRITICAL STEP)
    relative_url = f"{PUBLIC_BASE_URL}{unique_filename}" 
    
    try:
        # Pass the target to the helper function
        await update_image_url(db, owner_id, relative_url, target) 
    except Exception as e:
        print(f"Database URL save error: {e}")
        # Log the error but still return the URL if the file save succeeded
        pass 

    # 5. Return Public URL
    return {
        "filename": unique_filename,
        "url": relative_url
    }