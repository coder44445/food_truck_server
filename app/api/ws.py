from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.websockets import WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_db
from db.redis import get_redis_client
from api.dependencies import get_token_data
from db import schemas, services, models
from sqlalchemy import select
import json
import asyncio
import redis.asyncio as redis

router = APIRouter(tags=["WebSockets"])

# --- Constants for Presence ---
TRUCK_PRESENCE_KEY_PREFIX = "presence:truck:"
PRESENCE_TIMEOUT_SECONDS = 30 


# --- Dedicated WebSocket for Truck Location PUSH ---

@router.websocket("/ws/location/update")
async def websocket_location_update(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_async_db),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    truck_id = None

    token = websocket.query_params.get("token")

    try:
        # 1. Authentication and Setup
        token_data = await get_token_data(token=token)
        owner_id = token_data.user_id
        if token_data.role != 'truck':
            raise Exception("Access denied: Not a truck owner.")
            
        # Fetch the truck object
        truck_stmt = select(models.Truck).where(models.Truck.owner_user_id == owner_id)
        truck = (await db.execute(truck_stmt)).scalars().first()
        if not truck:
             raise Exception("Truck not linked to owner.")
        
        truck_id = truck.id
        await websocket.accept()
        print(f"Truck {truck_id} location push started.")

        # 2. Main Listener Loop
        while True:
            raw_data = await websocket.receive_text()
             
            location_dict = json.loads(raw_data)
            print(raw_data)
            location_update = schemas.TruckLocationUpdate(
                location=schemas.Point(
                    latitude=location_dict['latitude'],
                    longitude=location_dict['longitude']
                )
            )

            # A. Update PostGIS and Redis GeoSet (calls service function)
            await services.update_truck_location(db, redis_client, truck, location_update)
            print("updated in A")
            
            # B. CRITICAL: Update the presence key's TTL - Native await
            await redis_client.set(
                f"{TRUCK_PRESENCE_KEY_PREFIX}{truck_id}",
                "online",
                ex=PRESENCE_TIMEOUT_SECONDS
            )
            
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:

        print(f"Truck {truck_id} disconnected gracefully.")

    except Exception as e:
        print(f"Location WebSocket error for Truck {truck_id}: {e}")
    finally:
        # 3. CRITICAL Cleanup on Disconnect
        if truck_id is not None:
            print(f"Cleaning up location for Truck {truck_id}.")
            
            # A. Remove the location from the Redis GeoSet - Native await
            await redis_client.zrem(services.REDIS_GEO_KEY, str(truck_id))
            
            # B. Remove the presence key - Native await
            await redis_client.delete(f"{TRUCK_PRESENCE_KEY_PREFIX}{truck_id}")

            # C. Close the connection
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()


# --- Notification WebSocket Listener (Reads Pub/Sub) ---

@router.websocket("/ws/notifications")
async def websocket_notification_listener(
    websocket: WebSocket,
    token: str, 
    redis_client: redis.Redis = Depends(get_redis_client)
):
    
    # 1. Authenticate and Get User/Role (Logic remains the same)
    try:
        token_data = await get_token_data(token=token)
        user_id = token_data.user_id
        role = token_data.role
    except Exception as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid token: {e}")
        return

    # 2. Determine Channel Subscription
    pubsub = redis_client.pubsub()
    channel_to_subscribe = None

    if role == 'truck':
        channel_to_subscribe = f"{services.ORDER_CHANNEL_PREFIX}{user_id}"
    elif role == 'customer':
        channel_to_subscribe = f"{services.STATUS_CHANNEL_PREFIX}{user_id}"
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized role.")
        return

    # 3. Subscribe and Accept WS Connection
    await pubsub.subscribe(channel_to_subscribe)
    await websocket.accept()
    print(f"Notification WS accepted for {role}:{user_id} on channel {channel_to_subscribe}")

    try:
        # 4. Main Listener Loop (Asynchronous)
        while True:
            # wait_for_message() is an async blocking call, perfect for the event loop
            # Setting a timeout is important to prevent infinite blocking if Pub/Sub fails
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1) 
            
            if message and message['data']:
                # Forward the payload directly to the client
                await websocket.send_text(message['data'])
            
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        print(f"Notification WS disconnected for {role}:{user_id}")
    except Exception as e:
        print(f"Notification WS error for {role}:{user_id}: {e}")
    finally:
        # 5. Clean up
        await pubsub.unsubscribe(channel_to_subscribe)
