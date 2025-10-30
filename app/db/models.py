from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, DateTime, func, JSON
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from db.database import Base
from db.schemas import OrderStatus
import enum

# Custom Enum for User Roles
class UserRole(enum.Enum):
    customer = "customer"
    truck = "truck"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)

    # Relationship to the truck (One-to-One with Truck Owner)
    truck = relationship("Truck", back_populates="owner", uselist=False)

class TruckMovementStatus(enum.Enum):
    serving = "serving" # Stable location
    on_move = "on_move" # Live location required

class Truck(Base):
    __tablename__ = "trucks"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    is_active = Column(Boolean, default=False) # Truck is open for business
    movement_status = Column(Enum(TruckMovementStatus), default=TruckMovementStatus.serving, nullable=False)

    # PostGIS Column: Stores the current geographical point (SRID 4326 is WGS 84)
    # This is the single source of truth for location.
    location = Column(Geometry(geometry_type='POINT', srid=4326), nullable=True) 
    
    menu_json = Column(JSON, nullable=True)
    
    # Relationship back to the owner
    owner = relationship("User", back_populates="truck")
    
    # Relationship to orders
    orders = relationship("Order", back_populates="truck")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    items = Column(JSON, nullable=False) # Store the list of ordered items
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    truck = relationship("Truck", back_populates="orders")
    customer = relationship("User") # Relationship to the customer who placed the order