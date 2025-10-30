from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.elements import WKTElement
from db import models
from db import schemas
import redis.asyncio as redis
from typing import List
import json
import asyncio

# --- Constants ---
REDIS_GEO_KEY = "truck_locations_geo" # The key name for the Redis GeoSet
SRID_WGS84 = 4326 # Standard for GPS coordinates

ORDER_CHANNEL_PREFIX = "orders:truck:"    
STATUS_CHANNEL_PREFIX = "status:customer:" 

# --- Helper Functions ---

def point_to_wkt(lat: float, lon: float) -> str:
    """Converts lat/lon to WKT format (POINT(lon lat)). PostGIS uses (Longitude, Latitude)."""
    return f"POINT({lon} {lat})"

# --- Truck Location Management ---

async def update_truck_location(
    db: AsyncSession, 
    redis_client: redis.Redis,
    truck: models.Truck, 
    location_update: schemas.TruckLocationUpdate
) -> None:
    
    """
    Updates truck location in PostGIS (Source of Truth) and Redis (Cache).
    """
    print("updating truck location")
    
    lat = location_update.location.latitude
    lon = location_update.location.longitude
    
    # 1. Update PostGIS (Source of Truth)
    # The transaction ensures the commit is atomic
    truck.location = WKTElement(point_to_wkt(lat, lon), srid=SRID_WGS84)
    await db.commit()
    
    # 2. Update Redis (Geospatial Cache)
    # CRITICAL FIX: Use dictionary for geoadd for maximum async robustness
    
    await redis_client.geoadd(REDIS_GEO_KEY,(lon,lat,str(truck.id)))

    
    # 3. Update cached truck status/name for nearby search lookup
    # This ensures customer filtering is correct
    await redis_client.set(f"truck:{truck.id}:name", truck.name)
    await redis_client.set(f"truck:{truck.id}:is_active", str(truck.is_active))



async def find_nearby_trucks_redis(
    redis_client: redis.Redis, 
    search_query: schemas.NearbySearch
) -> List[schemas.Truck]:
    """
    Finds nearby trucks using the fast Redis GEOSEARCH command.
    """
    lat = search_query.location.latitude
    lon = search_query.location.longitude
    radius = search_query.radius_km
    
    # GEOSEARCH: Finds members within a circle defined by center (lon, lat) and radius
    # WITHCOORD returns lat/lon coordinates
    nearby_trucks_data = await redis_client.geosearch(
        REDIS_GEO_KEY,
        longitude=lon,
        latitude=lat,
        radius=radius,
        unit='km',
        withcoord=True,
        withdist=True
    )

    print(nearby_trucks_data)
    
    results = []
    
    # Data is returned as tuples: (truck_id, distance, (lon, lat))
    for truck_id_str, distance_km, (truck_lon, truck_lat) in nearby_trucks_data:
        truck_id = int(truck_id_str)
        
        # 1. Fetch cached 'is_active' status
        is_active_str = await redis_client.get(f"truck:{truck_id}:is_active")
        
        # CRITICAL FIX: Check explicitly against 'True' string, handling None/missing keys
        
        if is_active_str == 'True':
            name = await redis_client.get(f"truck:{truck_id}:name")
            
            results.append(schemas.Truck(
                id=truck_id,
                name=name,
                is_active=True,
                current_location=schemas.Point(latitude=truck_lat, longitude=truck_lon)
            ))
            
    return results

# --- Redis Pub/Sub Management (Real-Time) ---

async def publish_new_order(redis_client: redis.Redis, order: models.Order):
    """Publishes a notification when a new order is placed to the truck owner's channel."""
    
    message = {
        "order_id": order.id,
        "status": order.status.value,
        "message": f"New order #{order.id} received!",
        "customer_id": order.customer_id
    }
    
    channel_name = f"{ORDER_CHANNEL_PREFIX}{order.truck_id}"
    await redis_client.publish(channel_name, json.dumps(message))

async def publish_status_update(redis_client: redis.Redis, order: models.Order):
    """Publishes a notification when an order status is updated to the customer's channel."""
    
    message = {
        "order_id": order.id,
        "status": order.status.value,
        "message": f"Your order #{order.id} is now {order.status.value}.",
    }
    
    channel_name = f"{STATUS_CHANNEL_PREFIX}{order.customer_id}"
    await redis_client.publish(channel_name, json.dumps(message))