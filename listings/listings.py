from __future__ import annotations

from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from .address import AddressCreate, AddressRead

class ListingBase(BaseModel):
    title: str = Field(
        ...,
        description="Short listing title or headline.",
        json_schema_extra={"example": "2 Apartment Bedroom with Gym and Pool"},
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of the apartment.",
        json_schema_extra={"example": "Beautiful 2 bedroom apartment. Right by the park and 1 train"},
    )
    monthly_rent: float = Field(
        ...,
        description = "Monthly rent price in USD",
        json_schema_extra={"example": 1900.00},
    )
    num_bedrooms: int = Field(
        ...,
        description="Number of bedrooms",
        json_schema_extra={"example": 2},
    )
    num_bathrooms: int = Field(
        ...,
        description="Number of bathrooms",
        json_schema_extra={"example": 2},
    )
    square_feet: Optional[int] = Field(
        None,
        description="Total living area in square footage",
        json_schema_extra={"example": 1000},
    )
    amenities: List[str] = Field(
        default_factory=list,
        description="List of available amenities",
        json_schema_extra={"example": ["Gym", "Laundry", "Washer", "Dryer"]},
    )
    is_available: bool = Field(
        default=True,
        description="Whether the apartment is currently available",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Spacious 2-Bedroom Apartment in Downtown",
                    "description": "Modern apartment close to subway and restaurants.",
                    "monthly_rent": 2500.00,
                    "num_bedrooms": 2,
                    "num_bathrooms": 1.5,
                    "square_feet": 900,
                    "amenities": ["Gym", "Laundry", "Rooftop Access"],
                    "is_available": True,
                }
            ]
        }
    }

class ListingCreate(ListingBase):
    address: AddressCreate = Field(
        ...,
        description="Inline address to create with the listing",
    )

class ListingRead(ListingBase):
    id: UUID = Field(
        default_factory=uuid4,
        description="Persistent listing ID (server generated).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation of listing (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Most recently time listing was updated (UTC)",
    )

    address: AddressRead

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Spacious 2-Bedroom Apartment in Downtown",
                    "description": "Modern apartment close to subway and restaurants.",
                    "monthly_rent": 2500.00,
                    "num_bedrooms": 2,
                    "num_bathrooms": 1.5,
                    "square_feet": 900,
                    "amenities": ["Gym", "Laundry", "Rooftop Access"],
                    "is_available": True,
                    "created_at": "2025-10-06T12:00:00Z",
                    "updated_at": "2025-10-06T12:00:00Z",
                    "address": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "street": "123 Main St",
                        "city": "New York",
                        "state": "NY",
                        "postal_code": "10001",
                        "country": "USA"
                    }
                }
            ]
        },
    }









