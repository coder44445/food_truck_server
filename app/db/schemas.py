import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Any, List, Dict, Optional
from enum import Enum

# --- Geospatial and Location Models ---

class Point(BaseModel):
    """Represents a simple geographical point."""
    latitude: float
    longitude: float
    
class TruckLocationUpdate(BaseModel):
    """Data received when a truck updates its location."""
    location: Point

class NearbySearch(BaseModel):
    """Data received from a customer searching for trucks."""
    location: Point
    radius_km: float = 5.0
    
# --- Enum and Status ---

class OrderStatus(str, Enum):
    """Defines the lifecycle of an order."""
    pending = "pending"
    preparing = "preparing"
    ready_for_pickup = "ready_for_pickup"
    finished = "finished"
    cancelled = "cancelled"

# --- User/Auth Models ---
class UserBase(BaseModel):
    email: EmailStr
    
class UserCreate(UserBase):
    phone_number: str
    password: str
    
class TruckOwnerCreate(UserCreate):
    truck_name: str
    
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None
    
# --- Truck Models ---

class TruckBase(BaseModel):
    name: str
    is_active: bool = False  # Truck is open/closed

class Truck(TruckBase):
    id: int
    movement_status: str
    movement_status: Optional[str] = None
    current_location: Optional[Point] = None

    menu_json: Optional[Dict[str, Any]] = None
    profile_image_url: Optional[str] = None
    
    class Config:
        from_attributes = True
# --- Selected Items Models ---

class SelectedItem(BaseModel):
    item_id: UUID
    quantity: int

    def dict(self, *args, **kwargs):
      """Override dict method to convert UUID to string."""
      data = super().model_dump(*args, **kwargs)
      # Convert UUID to string for serialization
      data['item_id'] = str(data['item_id'])
      return data

class OrderIn(BaseModel):
    truck_id: int
    items: List[SelectedItem]

# --- Order Models ---

class OrderItem(BaseModel):
    item_id: UUID
    name: str
    quantity: int
    price: float


class Order(OrderIn):
    id: int
    customer_id: int
    status: OrderStatus
    created_at: datetime.datetime 
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() 
        }