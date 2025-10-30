from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_db
from db.redis import get_redis_client
from api.dependencies import get_current_customer, get_current_truck_owner, get_owner_truck
from db import schemas, models, services
from redis.asyncio import Redis
from sqlalchemy.future import  select

router = APIRouter(tags=["Orders"])

# --- Customer Endpoints ---
# 
@router.post("/orders/place", response_model=schemas.Order, status_code=status.HTTP_201_CREATED)
async def place_new_order(
    order_in: schemas.OrderIn,
    customer_id: int = Depends(get_current_customer), # Requires logged-in customer
    db: AsyncSession = Depends(get_async_db),
    redis: Redis = Depends(get_redis_client)
):
    """Customer places a new order notifies the truck owner."""

    # 1. Verify truck exists and is active 
    truck_stmt = select(models.Truck).where(models.Truck.id == order_in.truck_id, models.Truck.is_active == True)
    truck = (await db.execute(truck_stmt)).scalars().first()
    if not truck:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Truck not found or is closed.")

    # 2. Create the Order object
    db_order = models.Order(
        truck_id=order_in.truck_id,
        customer_id=customer_id,
        items=[item.dict() for item in order_in.items],
        status=models.OrderStatus.pending
    )

    for item in order_in.items:
        print(item)
    
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    
    # 3. Publish notification to the Truck Owner (Real-time alert)
    await services.publish_new_order(redis, db_order)
    
    return schemas.Order.model_validate(db_order)

# --- Truck Owner Endpoints ---

@router.get("/owner/orders/pending")
async def get_pending_orders(
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db)
):
    """Owner views all pending or preparing orders for their truck."""

    # Query to fetch pending or preparing orders
    stmt = select(models.Order).where(
        models.Order.truck_id == truck.id,
        models.Order.status.in_([models.OrderStatus.pending, models.OrderStatus.preparing])
    ).order_by(models.Order.created_at)

    # Execute query and fetch results
    orders = (await db.execute(stmt)).scalars().all()

    
    # Print the result for debugging purposes
    if not orders:
        print(f"No pending or preparing orders for truck with ID {truck.id}")
        raise HTTPException(status_code=404, detail="No pending or preparing orders found.")
    
    print(f"Found {len(orders)} pending or preparing orders for truck with ID {truck.id}")
    

    pending_orders = []

    for order in orders: 
        
        for item in order.items:
            order_id = order.id
            item_id = item["item_id"]
            name = truck.menu_json[item_id]["name"]
            quantity = item["quantity"]
            price = truck.menu_json[item_id]["price"]
            status = order.status

            ordered_item = {
                "order_id" : order_id,
                "item_id" : item_id,
                "name" : name,
                "quantity" : quantity,
                "price" : price,
                "status" : status
            }
            
            pending_orders.append(ordered_item)

    return pending_orders


@router.put("/owner/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    new_status: models.OrderStatus,
    truck: models.Truck = Depends(get_owner_truck),
    db: AsyncSession = Depends(get_async_db),
    redis: Redis = Depends(get_redis_client)
):
    """Owner updates the status of an order and notifies the customer."""
    
    # 1. Fetch and verify the order belongs to this truck
    stmt = select(models.Order).where(
        models.Order.id == order_id, 
        models.Order.truck_id == truck.id
    )
    order = (await db.execute(stmt)).scalars().first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or does not belong to your truck.")

    # 2. Update status and commit
    order.status = new_status
    await db.commit()
    await db.refresh(order)
    
    # 3. Publish notification to the Customer
    # Notifications are sent when status is updated to: preparing, ready_for_pickup, finished
    if new_status in [models.OrderStatus.preparing, models.OrderStatus.ready_for_pickup, models.OrderStatus.finished]:
        await services.publish_status_update(redis, order)

    preparing_orders = []
        
    for item in order.items:
        order_id = order.id
        item_id = item["item_id"]
        name = truck.menu_json[item_id]["name"]
        quantity = item["quantity"]
        price = truck.menu_json[item_id]["price"]
        status = order.status
        ordered_item = {
            "order_id" : order_id,
            "item_id" : item_id,
            "name" : name,
            "quantity" : quantity,
            "price" : price,
            "status" : status
        }
        
        preparing_orders.append(ordered_item)
    print
    return preparing_orders


@router.get("/orders", response_model=List[schemas.Order])
async def get_user_orders(
    customer_id: int = Depends(get_current_customer),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Retrieve all past and current orders for the logged-in customer.
    """
    stmt = select(models.Order).where(
        models.Order.customer_id == customer_id
    ).order_by(models.Order.created_at.desc()) # Show most recent first
    
    orders = (await db.execute(stmt)).scalars().all()
    
    if not orders:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No orders found for this user.")
        
    return [schemas.Order.model_validate(o) for o in orders]


@router.get("/orders/{order_id}", response_model=schemas.Order)
async def get_order_details(
    order_id: int,
    customer_id: int = Depends(get_current_customer),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Retrieve details for a specific order, ensuring it belongs to the logged-in customer.
    """
    stmt = select(models.Order).where(
        models.Order.id == order_id,
        models.Order.customer_id == customer_id
    )
    order = (await db.execute(stmt)).scalars().first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or you do not have permission to view it.")
        
    return schemas.Order.model_validate(order)
