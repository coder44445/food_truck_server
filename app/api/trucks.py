from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_db
from db.redis import get_redis_client
from api.dependencies import get_current_customer, get_current_truck_owner, get_owner_truck
from db import schemas, models, services
from redis import asyncio as redis
from typing import Any, Dict, List, Union

router = APIRouter(tags=["Trucks & Location"])

# --- Owner Endpoints ---

@router.get("/owner/truck-details", response_model=schemas.Truck)
async def fetch_owner_truck_details(
    # Requires the owner's token and fetches the truck linked to their user ID
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db) 
):
    """
    Fetches the specific truck details, status, and current location 
    for the authenticated owner (used by the owner dashboard on startup).
    """
    # The 'truck' object is already fetched by the get_owner_truck dependency
    # We validate and return it.

    return schemas.Truck.model_validate(truck)

@router.put("/owner/location", status_code=status.HTTP_204_NO_CONTENT)
async def update_owner_truck_location(
    location_update: schemas.TruckLocationUpdate,
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Owner updates their truck's current location (used when movement_status is 'on_move').
    Updates PostGIS and Redis Cache.
    """
    # CRITICAL: Ensures we pass the redis client
    await services.update_truck_location(db, redis_client, truck, location_update)
    print("working")
    return 

@router.put("/owner/status")
async def toggle_truck_status(
    is_active: bool,
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db),
    redis_client: redis.Redis = Depends(get_redis_client) # Inject Redis
) -> schemas.Truck:
    """
    Owner opens or closes their truck for business.
    """
    truck.is_active = is_active
    print(truck.name,truck.is_active)
    await db.commit()
   
    await redis_client.set(f"truck:{truck.id}:is_active", str(is_active))

    # Also update truck name in case it wasn't cached before
    await redis_client.set(f"truck:{truck.id}:name", truck.name)
    
    # If setting to active, ensure location is added to GeoSet if present in DB
    if is_active and truck.location:
        # NOTE: If we used the location update endpoint, this would be cleaner.
        # But for reliability, we ensure the truck appears in the GEOSET if active.
        # This requires pulling the location coordinates from the PostGIS object first.
        
        # Simplified logic: If the truck is active, and has a location, ensure it's in the GeoSet
        # This is typically handled by the WS PING, but we add a fallback check here.
        pass # The owner's first ping after opening will ensure GeoSet population

    return schemas.Truck.model_validate(truck)

# --- Customer Endpoints ---

@router.post("/trucks/nearby")
async def search_nearby_trucks(
    search_query: schemas.NearbySearch,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """
    Customer searches for active trucks within a radius using the fast Redis cache.
    
    """

    if search_query.radius_km > 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum search radius is 15km."
        )

    nearby_trucks = await services.find_nearby_trucks_redis(redis_client, search_query)

    print(nearby_trucks)
    
    if not nearby_trucks:
        return {"details" : "No active trucks found in this radius"}
        
    return nearby_trucks


# --- Menu Management Endpoints ---
@router.get("/owner/menu", response_model=Union[Dict[str, Any], None])
async def get_owner_menu(
    truck: models.Truck = Depends(get_owner_truck),
):
    """Owner fetches their current menu."""
    if truck.menu_json is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not set for this truck."
        )
    # SQLAlchemy returns the JSON field as a Python dict/list automatically


    return truck.menu_json

@router.patch("/owner/menu/items", response_model=Dict[str, Any])
async def patch_owner_menu_items(
    new_item: Dict[str, Any],
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Owner updates existing items or adds new items to the menu.
    Assumes menu_json is a dictionary mapping item IDs/names to item details.
    """
    if truck.menu_json is None:
        truck.menu_json = {}
        
    current_menu = truck.menu_json.copy()

    print(new_item)

    item_id = new_item.get("item_id")
    if item_id:
        # Merge the new item data with existing item data (or add new item)
        current_menu[item_id] = {**(current_menu.get(str(item_id)) or {}), **new_item}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Each new item must contain an 'id' key for patching."
        )
            
    truck.menu_json = current_menu
    await db.commit()
    
    return truck.menu_json

@router.delete("/owner/menu/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owner_menu_item(
    item_id: str,
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db),
):
    """Owner deletes a specific item from the menu by ID."""
    if truck.menu_json is None or item_id not in truck.menu_json :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID '{item_id}' not found in the menu."
        )
    
    updated_menu = truck.menu_json.copy()
    updated_menu.pop(item_id, None)  # Safe removal
    truck.menu_json = updated_menu   # Triggers ORM to mark as "dirty"
    await db.commit()
    return {"message": "Item deleted successfully"}

@router.get("/truck/{truck_id}/menu", response_model=Union[Dict[str, Any], None])
async def get_menu_by_truck_id(
    truck_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Customer fetches the menu for a specific truck by its ID.
    """
    result = await db.execute(
        select(models.Truck).where(models.Truck.id == truck_id)
    )
    print(truck_id)
    truck = result.scalars().first()

    if truck is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Truck not found."
        )
    
    if truck.menu_json is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not available for this truck."
        )
    
    return truck.menu_json
