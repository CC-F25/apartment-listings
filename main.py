from __future__ import annotations

import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    status,
    BackgroundTasks,
    Response,
    Header,
    Query,
    Path,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from listings.listings import ListingCreate, ListingRead, ListingUpdate
from listings.address import AddressCreate, AddressRead
from database import Base, engine, get_db, SessionLocal
from listings.listings_sql import AddressDB, ListingDB

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------#
# DB setup
# -----------------------------------------------------------------------------#

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# task queue for async listing creation
task_queue: Dict[UUID, Dict] = {}

# -----------------------------------------------------------------------------#
# FastAPI app
# -----------------------------------------------------------------------------#

app = FastAPI(
    title="Listings/Address API",
    description="FastAPI app using Pydantic v2 models + SQLAlchemy for Listings microservice",
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

# -----------------------------------------------------------------------------#
# Helper functions
# -----------------------------------------------------------------------------#

def amenities_to_string(amenities: Optional[List[str]]) -> Optional[str]:
    if not amenities:
        return None
    return ",".join(amenities)

def amenities_from_string(s: Optional[str]) -> List[str]:
    if not s:
        return []
    return [a.strip() for a in s.split(",") if a.strip()]

def make_address_db(db: Session, addr_in: AddressCreate) -> AddressDB:
    """Create and persist an AddressDB row from an AddressCreate payload."""
    addr = AddressDB(
        street=addr_in.street,
        city=addr_in.city,
        state=addr_in.state,
        postal_code=addr_in.postal_code,
        country=addr_in.country,
    )
    db.add(addr)
    db.flush()  # assigns addr.id from default
    return addr

def listing_db_to_read(listing: ListingDB) -> ListingRead:
    """Convert a ListingDB (with joined AddressDB) into a ListingRead Pydantic model."""
    addr = listing.address
    address_read = AddressRead(
        id=UUID(addr.id),
        street=addr.street,
        city=addr.city,
        state=addr.state,
        postal_code=addr.postal_code,
        country=addr.country,
        created_at=addr.created_at,
        updated_at=addr.updated_at,
    )
    return ListingRead(
        id=UUID(listing.id),
        title=listing.title,
        description=listing.description,
        monthly_rent=listing.monthly_rent,
        num_bedrooms=listing.num_bedrooms,
        num_bathrooms=listing.num_bathrooms,
        square_feet=listing.square_feet,
        amenities=amenities_from_string(listing.amenities),
        is_available=listing.is_available,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        address=address_read,
    )

def compute_listing_etag(listing) -> str:
    """Compute ETag from a ListingDB or ListingRead (needs id + updated_at)."""
    ts = int(listing.updated_at.timestamp())
    # Weak ETag, includes id + last updated timestamp
    return f'W/"{listing.id}-{ts}"'

# -----------------------------------------------------------------------------#
# Long-running async listing creation (for /listings/async)
# -----------------------------------------------------------------------------#

async def long_running_listing_creation(payload: ListingCreate, task_id: UUID):
    """Simulate a long-running DB operation and store ListingRead in task_queue."""
    await asyncio.sleep(5)  # simulate heavy work

    db = SessionLocal()
    try:
        addr = make_address_db(db, payload.address)
        listing = ListingDB(
            title=payload.title,
            description=payload.description,
            monthly_rent=payload.monthly_rent,
            num_bedrooms=payload.num_bedrooms,
            num_bathrooms=payload.num_bathrooms,
            square_feet=payload.square_feet,
            amenities=amenities_to_string(payload.amenities),
            is_available=payload.is_available,
            address_id=addr.id,
        )
        db.add(listing)
        db.commit()
        db.refresh(listing)
        db.refresh(addr)

        task_queue[task_id]["result"] = listing_db_to_read(listing)
        task_queue[task_id]["status"] = "COMPLETED"
    except Exception as e:
        db.rollback()
        task_queue[task_id]["error"] = str(e)
        task_queue[task_id]["status"] = "FAILED"
    finally:
        db.close()

# -----------------------------------------------------------------------------#
# Listing endpoints
# -----------------------------------------------------------------------------#

@app.post("/listings", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
async def create_listing(payload: ListingCreate, db: Session = Depends(get_db)):
    """Create a listing + address row in MySQL and return a ListingRead."""
    await asyncio.sleep(0.1)  # simulate DB latency

    addr = make_address_db(db, payload.address)

    listing = ListingDB(
        title=payload.title,
        description=payload.description,
        monthly_rent=payload.monthly_rent,
        num_bedrooms=payload.num_bedrooms,
        num_bathrooms=payload.num_bathrooms,
        square_feet=payload.square_feet,
        amenities=amenities_to_string(payload.amenities),
        is_available=payload.is_available,
        address_id=addr.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    db.refresh(addr)

    return listing_db_to_read(listing)

# Asynchronous POST with 202 + polling
@app.post("/listings/async", status_code=status.HTTP_202_ACCEPTED)
async def create_listing_async(
    payload: ListingCreate,
    background_tasks: BackgroundTasks,
    response: Response,
):
    task_id = UUID(os.urandom(16).hex())
    task_queue[task_id] = {"status": "PENDING", "result": None, "error": None}

    background_tasks.add_task(long_running_listing_creation, payload, task_id)

    response.headers["Location"] = f"/listings/status/{task_id}"
    return {
        "message": f"Listing creation process started for task {task_id}.",
        "task_id": task_id,
    }

@app.get("/listings/status/{task_id}")
async def get_listing_creation_status(task_id: UUID):
    """Check status of async listing creation task."""
    await asyncio.sleep(0.01)

    task = task_queue.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task ID not found.")

    if task["status"] == "COMPLETED":
        return task["result"]
    if task["status"] == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=task["error"],
        )
    return {"status": "PENDING", "message": "The listing creation is still in progress."}

# GET collection with filters
@app.get("/listings", response_model=List[ListingRead])
async def list_listings(
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
    db: Session = Depends(get_db),
):
    await asyncio.sleep(0.2)

    query = db.query(ListingDB).join(ListingDB.address)

    # numeric filters at DB-level
    if min_rent is not None:
        query = query.filter(ListingDB.monthly_rent >= min_rent)
    if max_rent is not None:
        query = query.filter(ListingDB.monthly_rent <= max_rent)
    if min_bedrooms is not None:
        query = query.filter(ListingDB.num_bedrooms >= min_bedrooms)
    if max_bedrooms is not None:
        query = query.filter(ListingDB.num_bedrooms <= max_bedrooms)
    if min_bathrooms is not None:
        query = query.filter(ListingDB.num_bathrooms >= min_bathrooms)
    if max_bathrooms is not None:
        query = query.filter(ListingDB.num_bathrooms <= max_bathrooms)
    if min_sqft is not None:
        query = query.filter(ListingDB.square_feet >= min_sqft)
    if max_sqft is not None:
        query = query.filter(ListingDB.square_feet <= max_sqft)
    if is_available is not None:
        query = query.filter(ListingDB.is_available == is_available)
    if city:
        query = query.filter(AddressDB.city.ilike(city))
    if state:
        query = query.filter(AddressDB.state.ilike(state))

    listings = query.all()

    # in-memory amenities filtering
    if amenities:
        listings = [
            l for l in listings
            if all(a in amenities_from_string(l.amenities) for a in amenities)
        ]

    return [listing_db_to_read(l) for l in listings]

@app.put("/listings/{listing_id}", response_model=ListingRead)
async def update_listing(
    listing_id: UUID,
    payload: ListingCreate,  # or ListingUpdate if you want partial later
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: Session = Depends(get_db),
):
    await asyncio.sleep(0.05)

    listing = (
        db.query(ListingDB)
        .join(ListingDB.address)
        .filter(ListingDB.id == str(listing_id))
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    current_etag = compute_listing_etag(listing)
    if if_match is not None and if_match != current_etag:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="ETag mismatch; the listing has been modified by another process.",
        )

    # Update address
    addr = listing.address
    addr.street = payload.address.street
    addr.city = payload.address.city
    addr.state = payload.address.state
    addr.postal_code = payload.address.postal_code
    addr.country = payload.address.country
    addr.updated_at = datetime.utcnow()

    # Update listing fields
    listing.title = payload.title
    listing.description = payload.description
    listing.monthly_rent = payload.monthly_rent
    listing.num_bedrooms = payload.num_bedrooms
    listing.num_bathrooms = payload.num_bathrooms
    listing.square_feet = payload.square_feet
    listing.amenities = amenities_to_string(payload.amenities)
    listing.is_available = payload.is_available
    listing.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(listing)
    db.refresh(addr)

    return listing_db_to_read(listing)

@app.get("/listings/{listing_id}", response_model=ListingRead)
async def get_listing(
    listing_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
):
    await asyncio.sleep(0.05)

    listing = (
        db.query(ListingDB)
        .join(ListingDB.address)
        .filter(ListingDB.id == str(listing_id))
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    etag = compute_listing_etag(listing)
    response.headers["ETag"] = etag

    return listing_db_to_read(listing)

@app.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(listing_id: UUID, db: Session = Depends(get_db)):
    await asyncio.sleep(0.1)

    listing = db.query(ListingDB).filter(ListingDB.id == str(listing_id)).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    db.delete(listing)
    db.commit()
    # 204: no body
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# -----------------------------------------------------------------------------#
# Root
# -----------------------------------------------------------------------------#
@app.get("/")
def root():
    return {"message": "Welcome to the Listings/Address API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------#
# Entrypoint
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
