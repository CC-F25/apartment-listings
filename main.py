from __future__ import annotations

import os
import socket
from datetime import datetime

from typing import Dict, List
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi import Query, Path
from typing import Optional

from listings.listings import ListingCreate, ListingRead, ListingUpdate
from listings.address import AddressCreate, AddressRead

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# Fake in-memory "databases"
# -----------------------------------------------------------------------------

listings_db: Dict[UUID, ListingRead] = {}

app = FastAPI(
    title="Person/Address API",
    description="Demo FastAPI app using Pydantic v2 models for Person and Address",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Helper functions for address
# -----------------------------------------------------------------------------

def make_address_read(addr: AddressCreate) -> AddressRead:
    now = datetime.utcnow()
    return AddressRead(
        id=uuid4(),
        street=addr.street,
        city=addr.city,
        state=addr.state,
        postal_code=addr.postal_code,
        country=addr.country,
        created_at=now,
        updated_at=now,
    )


def make_listing_read(payload: ListingCreate) -> ListingRead:
    now = datetime.utcnow()
    return ListingRead(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        monthly_rent=payload.monthly_rent,
        num_bedrooms=payload.num_bedrooms,
        num_bathrooms=payload.num_bathrooms,
        square_feet=payload.square_feet,
        amenities=payload.amenities or [],
        is_available=payload.is_available,
        address=make_address_read(payload.address),
        created_at=now,
        updated_at=now,
    )

# -----------------------------------------------------------------------------
# Listing endpoints
# -----------------------------------------------------------------------------

@app.post("/listings", response_model=ListingRead, status_code=201)
def create_listing(payload: ListingCreate):
    listing = make_listing_read(payload)
    if listing.id in listings_db:
        raise HTTPException(status_code=400, detail="Listing with this ID already exists")
    listings_db[listing.id] = listing
    return listings_db[listing.id]

@app.get("/listings", response_model=List[ListingRead])
def list_listings(
    min_rent: Optional[float] = Query(None, description="Minimum monthly rent in USD"),
    max_rent: Optional[float] = Query(None, description="Maximum monthly rent in USD"),
    min_bedrooms: Optional[int] = Query(None, description="Minimum number of bedrooms"),
    max_bedrooms: Optional[int] = Query(None, description="Maximum number of bedrooms"),
    min_bathrooms: Optional[float] = Query(None, description="Minimum number of bathrooms"),
    max_bathrooms: Optional[float] = Query(None, description="Maximum number of bathrooms"),
    min_sqft: Optional[int] = Query(None, description="Minimum square footage"),
    max_sqft: Optional[int] = Query(None, description="Maximum square footage"),
    amenities: Optional[List[str]] = Query(
        None,
        description="Filter by required amenities (e.g. amenities=Gym&amenities=Pool)",
    ),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state/region"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
):
    results = list(listings_db.values())

    if min_rent is not None:
        results = [l for l in results if l.monthly_rent >= min_rent]
    if max_rent is not None:
        results = [l for l in results if l.monthly_rent <= max_rent]
    if min_bedrooms is not None:
        results = [l for l in results if l.num_bedrooms >= min_bedrooms]
    if max_bedrooms is not None:
        results = [l for l in results if l.num_bedrooms <= max_bedrooms]
    if min_bathrooms is not None:
        results = [l for l in results if l.num_bathrooms >= min_bathrooms]
    if max_bathrooms is not None:
        results = [l for l in results if l.num_bathrooms <= max_bathrooms]
    if min_sqft is not None:
        results = [l for l in results if (l.square_feet or 0) >= min_sqft]
    if max_sqft is not None:
        results = [l for l in results if (l.square_feet or 0) <= max_sqft]
    if is_available is not None:
        results = [l for l in results if l.is_available == is_available]
    
    if amenities:
        results = [l for l in results if all(a in l.amenities for a in amenities)]

    if city:
        results = [l for l in results if l.address.city.lower() == city.lower()]
    if state:
        results = [l for l in results if l.address.state and l.address.state.lower() == state.lower()]

    return results

@app.put("/listings/{listing_id}", response_model=ListingRead)
def update_listing(listing_id: UUID, payload: ListingCreate):  
    existing = listings_db.get(listing_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Listing not found")

    new_address = make_address_read(payload.address)

    new_listing = ListingRead(
        id=listing_id,
        title=payload.title,
        description=payload.description,
        monthly_rent=payload.monthly_rent,
        num_bedrooms=payload.num_bedrooms,
        num_bathrooms=payload.num_bathrooms,
        square_feet=payload.square_feet,
        amenities=payload.amenities,
        is_available=payload.is_available,
        address=new_address,                    
        created_at=existing.created_at,        
        updated_at=datetime.utcnow(),           
    )

    listings_db[listing_id] = new_listing
    return new_listing

@app.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: UUID):
    if listing_id not in listings_db:
        raise HTTPException(status_code=404, detail="Course no found.")
    del listings_db[listing_id]
    
# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Person/Address API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint for `python main.py`
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)