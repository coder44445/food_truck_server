from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Annotated

# --- Request Schemas (Data coming INTO the API) ---

class GeoQuery(BaseModel):
    """
    Schema for the user's location and search parameters. 
    FastAPI automatically validates the request body against this model.
    """
    # Latitude: Must be between -90 and 90
    Annotated[float, Field(strict=True, gt=0)]
    user_lat: Annotated[float,Field(ge=-90.0, le=90.0,description="User's current latitude.")]
    # Longitude: Must be between -180 and 180
    user_lon: Annotated[float,Field(ge=-180.0, le=180.0,description="User's current longitude.")]

    # Radius in meters: Minimum 100m, default 5000m (5km), max 20000m (20km)
    radius_meters: Annotated[float,Field(5000,ge=100, le=20000, description="Search radius in meters (100 to 20000).")]
    limit: Annotated[int,Field(20,ge=1, le=100, description="Maximum number of trucks to return.")]

class TruckLocationUpdate(BaseModel):
    """
    Schema for truck owners updating their real-time location.
    Requires owner_id (for authentication) and current coordinates.
    """
    owner_id: str = Field(..., description="Unique ID of the truck owner/user (from Auth provider).")
    # Coordinates for the truck's new position
    current_lat: Annotated[float,Field(ge=-90.0, le=90.0)]
    current_lon: Annotated[float,Field(ge=-180.0, le=180.0)]
    
# --- Response Schemas (Data going OUT of the API) ---

class TruckOut(BaseModel):
    """
    Schema for a single truck returned to the client, including the calculated distance.
    """
    id: str
    name: str
    cuisine_type: Optional[str]
    is_open: bool
    rating: float
    distance_meters: float = Field(..., description="Calculated distance from the user to the truck (in meters).")

class NearbyResponse(BaseModel):
    """
    Root response schema for the nearby search endpoint.
    """
    search_radius_m: int
    trucks: list[TruckOut]

# --- New Real-time Message Schema ---

class RealtimeLocationMessage(BaseModel):
    """
    Schema for the data published to Redis and sent to WebSocket clients.
    """
    owner_id: str = Field(..., description="The ID of the truck that moved.")
    lat: float
    lon: float
    timestamp: float = Field(..., description="Unix timestamp of the update.")
    
    class Config:
        # Allows conversion from ORM object (like a dict) to Pydantic model
        from_attributes = True
# app/db/schemas.py (Additions)

# --- User Creation Models ---
class UserBase(BaseModel):
    email: EmailStr  # Pydantic's built-in email validation
    
class UserCreate(UserBase):
    password: str
    
class CustomerCreate(UserCreate):
    # No extra fields needed for basic customer
    pass

class TruckOwnerCreate(UserCreate):
    phone_number: str
    truck_name: str
    # Note: We skip image uploads for now, assuming base64 or separate upload later
    
# --- Login and Token Models ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None
    
# --- User/Truck Read Models (Updates) ---
class User(UserBase):
    id: int
    role: str
    phone_number: Optional[str] = None
    
    class Config:
        from_attributes = True
        
# Update Truck model to include owner details if needed for read operations
# ... (existing Truck model)