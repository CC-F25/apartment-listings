# listings/listings_sql.py
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database import Base


class AddressDB(Base):
    __tablename__ = "addresses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    street = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # one address can have many listings
    listings = relationship("ListingDB", back_populates="address")


class ListingDB(Base):
    __tablename__ = "listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    monthly_rent = Column(Float, nullable=False)
    num_bedrooms = Column(Integer, nullable=False)
    num_bathrooms = Column(Integer, nullable=False)
    square_feet = Column(Integer, nullable=True)

    # Simple approach: store amenities as a comma-separated string
    # (we can parse it to/from List[str] in code if needed)
    amenities = Column(Text, nullable=True)

    is_available = Column(Boolean, nullable=False, default=True)

    address_id = Column(String(36), ForeignKey("addresses.id"), nullable=False)
    address = relationship("AddressDB", back_populates="listings")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
