from __future__ import annotations

import os
import asyncio # New import for simulation
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4
import time

from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Response
from fastapi import Query, Path

from listings.listings import ListingCreate, ListingRead, ListingUpdate
from listings.address import AddressCreate, AddressRead

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# Fake in-memory "databases" and Task Queue (Simulating SQL Storage)
# -----------------------------------------------------------------------------

# This dictionary now conceptually represents the ASYNC SQL DB storage
listings_db: Dict[UUID, ListingRead] = {}

# Dictionary to store the status of long-running tasks:
task_queue: Dict[UUID, Dict] = {}


app = FastAPI(
    title="Person/Address API",
    description="Demo FastAPI app using Pydantic v2 models for Person and Address",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Helper functions (Remain Synchronous, as they are CPU-bound Pydantic ops)
# -----------------------------------------------------------------------------

def make_address_read(addr: AddressCreate) -> AddressRead:
    # ... (same as before)
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
    # ... (same as before)
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
# Long-running task for Polling
# -----------------------------------------------------------------------------

async def long_running_listing_creation(payload: ListingCreate, task_id: UUID):
    """Simulates a long-running, asynchronous database operation for 202 Polling. To be modified when cloud database is done"""
    
    await asyncio.sleep(5) 
    
    try:
        # 1. Create the listing object
        listing = make_listing_read(payload)

        # 2. Simulate async write to DB (using dict for simplicity)
        listings_db[listing.id] = listing 

        # 3. Update task status
        task_queue[task_id]["result"] = listing
        task_queue[task_id]["status"] = "COMPLETED"
    except Exception as e:
        task_queue[task_id]["error"] = str(e)
        task_queue[task_id]["status"] = "FAILED"


# -----------------------------------------------------------------------------
# Listing endpoints (functions involving DB access are async)
# -----------------------------------------------------------------------------

@app.post("/listings", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
async def create_listing(payload: ListingCreate):    
    # Simulate the non-blocking I/O wait time for the INSERT query
    await asyncio.sleep(0.1) 
    
    listing = make_listing_read(payload)
    if listing.id in listings_db:
        raise HTTPException(status_code=400, detail="Listing with this ID already exists")
        
    # Simulate DB write
    listings_db[listing.id] = listing
    return listings_db[listing.id]

## Asynchronous POST with 202 Accepted and Polling
@app.post("/listings/async", status_code=status.HTTP_202_ACCEPTED)
async def create_listing_async(
    payload: ListingCreate,
    background_tasks: BackgroundTasks,
    response: Response,
):

    task_id = uuid4()
    task_queue[task_id] = {"status": "PENDING", "result": None, "error": None}
    
    # Schedule the long-running async task in the background
    background_tasks.add_task(long_running_listing_creation, payload, task_id)
    
    # Set the Location header for polling
    response.headers["Location"] = f"/listings/status/{task_id}"
    
    return {"message": f"Listing creation process started for task {task_id}.", "task_id": task_id}

## Polling Endpoint
@app.get("/listings/status/{task_id}")
async def get_listing_creation_status(task_id: UUID):
    """Endpoint to check the status of an asynchronous listing creation task."""
    
    # Simulate non-blocking I/O wait for checking status in a status table
    await asyncio.sleep(0.01)

    task = task_queue.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task ID not found.")
        
    status_code = task["status"]
    
    if status_code == "COMPLETED":
        return task["result"]
    elif status_code == "FAILED":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=task["error"])
    else:
        return {"status": "PENDING", "message": "The listing creation is still in progress."}


## GET Listings
@app.get("/listings", response_model=List[ListingRead])
async def list_listings(
    min_rent: Optional[float] = Query(None, description="Minimum monthly rent in USD"),
    max_rent: Optional[float] = Query(None, description="Maximum monthly rent in USD"),
    amenities: Optional[List[str]] = Query(
        None,
        description="Filter by required amenities (e.g. amenities=Gym&amenities=Pool)",
    ),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state/region"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
):
        
    await asyncio.sleep(0.2) 

    results = list(listings_db.values())

    if min_rent is not None:
        results = [l for l in results if l.monthly_rent >= min_rent]
    
    return results

## PUT Listing (Converted to Async)
@app.put("/listings/{listing_id}", response_model=ListingRead)
async def update_listing(listing_id: UUID, payload: ListingCreate):      
    await asyncio.sleep(0.05) 
    
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
    
    await asyncio.sleep(0.1) 
    
    listings_db[listing_id] = new_listing
    return new_listing

## GET Listing by ID
@app.get("/listings/{listing_id}", response_model=ListingRead)
async def get_listing(listing_id: UUID):
    """Retrieve a single listing, converted to async for DB access."""
    
    await asyncio.sleep(0.05) 
    
    listing = listings_db.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing

## DELETE Listing
@app.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(listing_id: UUID):
    
    await asyncio.sleep(0.1) 

    if listing_id not in listings_db:
        # Check before deleting is a SELECT query
        raise HTTPException(status_code=404, detail="Listing not found.")
        
    # Actual deletion (a DELETE query)
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