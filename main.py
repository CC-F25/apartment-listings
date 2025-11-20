from __future__ import annotations

import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import (
    FastAPI,
    HTTPException,
    status,
    BackgroundTasks,
    Response,
    Header,
    Query,
    Path,
)
from fastapi.middleware.cors import CORSMiddleware

from listings.listings import ListingCreate, ListingRead, ListingUpdate
from listings.address import AddressCreate, AddressRead

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# Fake in-memory "databases" and Task Queue (Simulating SQL Storage)
# -----------------------------------------------------------------------------

listings_db: Dict[UUID, ListingRead] = {}
task_queue: Dict[UUID, Dict] = {}

app = FastAPI(
    title="Listings/Address API",
    description="Demo FastAPI app using Pydantic v2 models for Listings and Address",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",                     # Firebase local emulator
        "https://cloud-computing-ui.web.app",        # deployed Firebase site
        "https://cloud-computing-ui.firebaseapp.com" # alt Firebase domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Helper functions
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
    listing_id = uuid4()
    addr = make_address_read(payload.address)
    return ListingRead(
        id=listing_id,
        title=payload.title,
        description=payload.description,
        monthly_rent=payload.monthly_rent,
        num_bedrooms=payload.num_bedrooms,
        num_bathrooms=payload.num_bathrooms,
        square_feet=payload.square_feet,
        amenities=payload.amenities or [],
        is_available=payload.is_available,
        address=addr,
        created_at=now,
        updated_at=now,
        links={
            "self": listing_self_path(listing_id),
        }
    )


def compute_listing_etag(listing: ListingRead) -> str:
    
    # etag based on listing id and timestamp of last update
    ts = int(listing.updated_at.timestamp())
    return f'W/"{listing.id}-{ts}"'

def listing_self_path(listing_id: UUID) -> str:
    return f"/listings/{listing_id}"

def listing_status_path(task_id: UUID) -> str:
    return f"/listings/status/{task_id}"

# -----------------------------------------------------------------------------
# Long-running task for async listing creation (202 + polling)
# -----------------------------------------------------------------------------

async def long_running_listing_creation(payload: ListingCreate, task_id: UUID):
    """Simulates a long-running, asynchronous database operation for 202 polling."""
    await asyncio.sleep(5)

    try:
        listing = make_listing_read(payload)
        listings_db[listing.id] = listing
        task_queue[task_id]["result"] = listing
        task_queue[task_id]["status"] = "COMPLETED"
    except Exception as e:
        task_queue[task_id]["error"] = str(e)
        task_queue[task_id]["status"] = "FAILED"


# -----------------------------------------------------------------------------
# Listing endpoints
# -----------------------------------------------------------------------------

# Synchronous-style create, but implemented as async to simulate DB I/O
@app.post("/listings", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    response: Response,
):

    await asyncio.sleep(0.1)  # simulate DB insert latency

    listing = make_listing_read(payload)
    if listing.id in listings_db:
        raise HTTPException(status_code=400, detail="Listing with this ID already exists")
    listings_db[listing.id] = listing

    response.headers["Location"] = listing_self_path(listing.id)

    return listings_db[listing.id]


# Asynchronous POST with 202 Accepted and polling
@app.post("/listings/async", status_code=status.HTTP_202_ACCEPTED)
async def create_listing_async(
    payload: ListingCreate,
    background_tasks: BackgroundTasks,
    response: Response,
):
    task_id = uuid4()
    task_queue[task_id] = {"status": "PENDING", "result": None, "error": None}

    background_tasks.add_task(long_running_listing_creation, payload, task_id)

    response.headers["Location"] = listing_status_path(task_id)
    return {
        "message": f"Listing creation process started for task {task_id}.",
        "task_id": task_id,
    }


@app.get("/listings/status/{task_id}")
async def get_listing_creation_status(task_id: UUID):
    """Check the status of an asynchronous listing creation task."""
    await asyncio.sleep(0.01)

    task = task_queue.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task ID not found.")

    status_code = task["status"]
    if status_code == "COMPLETED":
        return task["result"]
    elif status_code == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=task["error"],
        )
    else:
        return {"status": "PENDING", "message": "The listing creation is still in progress."}


# GET listings with filters (simplified)
@app.get("/listings", response_model=List[ListingRead])
async def list_listings(
    # pagination
    limit: int = Query(10, ge=1, le=100, description="Maximum number of listings to return"),
    offset: int = Query(0, ge=0, description="Number of listings to skip from the start"),
    # filters   
    num_bedrooms: Optional[int] = Query(None, description="Filter by number of bedrooms"),
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

    if num_bedrooms is not None:
        results = [l for l in results if l.num_bedrooms == num_bedrooms]
    if min_rent is not None:
        results = [l for l in results if l.monthly_rent >= min_rent]
    if max_rent is not None:
        results = [l for l in results if l.monthly_rent <= max_rent]
    if is_available is not None:
        results = [l for l in results if l.is_available == is_available]
    if amenities:
        results = [l for l in results if all(a in l.amenities for a in amenities)]
    if city:
        results = [l for l in results if l.address.city.lower() == city.lower()]
    if state:
        results = [
            l
            for l in results
            if l.address.state and l.address.state.lower() == state.lower()
        ]

    # pagination
    paged_results = results[offset: offset + limit]
    return paged_results


@app.put("/listings/{listing_id}", response_model=ListingRead)
async def update_listing(
    listing_id: UUID,
    payload: ListingCreate,
    if_match: Optional[str] = Header(None, alias="If-Match"),
):
    await asyncio.sleep(0.05)

    existing = listings_db.get(listing_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # etag concurrency check
    current_etag = compute_listing_etag(existing)
    if if_match is not None and if_match != current_etag:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="ETag mismatch; the listing has been modified by another process.",
        )

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


@app.get("/listings/{listing_id}", response_model=ListingRead)
async def get_listing(listing_id: UUID, response: Response):
    await asyncio.sleep(0.05)

    listing = listings_db.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # creating an etag for the information
    etag = compute_listing_etag(listing)
    response.headers["ETag"] = etag
    return listing


# DELETE listing
@app.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(listing_id: UUID):
    await asyncio.sleep(0.1)

    if listing_id not in listings_db:
        raise HTTPException(status_code=404, detail="Listing not found.")

    del listings_db[listing_id]


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Listings/Address API. See /docs for OpenAPI UI."}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
