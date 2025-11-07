"""
FastAPI backend for AA Flight Scraper
"""

import json
import os

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from scraper.scraper import scrape_flights

from .database import (complete_scrape, create_scrape, delete_scrape,
                       fail_scrape, get_all_scrapes, get_current_job_id,
                       get_latest_completed, get_running_scrape, get_scrape,
                       init_db, is_scrape_running, try_start_scrape)
from .models import (ComparisonResponse, ScrapeListItem, ScrapeRequest,
                     ScrapeResponse, ScrapeStatus)

# Initialize FastAPI app
app = FastAPI(
    title="FareCraft API",
    description="Award Flight Optimizer - Scrape American Airlines flight pricing and calculate CPP",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")


def run_scrape_job(
    job_id: int,
    origin: str,
    destination: str,
    date: str,
    passengers: int,
):
    """
    Background task to run the scraping job.
    Uses database-only locking to prevent concurrent scrapes.
    """
    try:
        # Try to atomically start this scrape
        # This checks if another scrape is running and updates status in one transaction
        if not try_start_scrape(job_id):
            fail_scrape(job_id, "Another scrape is already running")
            return

        # Run scraper (status is already set to 'running' by try_start_scrape)
        # Always scrape Main cabin (economy class) as per contest requirements
        results = scrape_flights(origin, destination, date, passengers, "economy")

        # Save results
        complete_scrape(job_id, results)

    except Exception as e:
        # Mark as failed
        fail_scrape(job_id, str(e))
        print(f"❌ Scrape {job_id} failed: {str(e)}")


@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML"""
    frontend_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(frontend_path)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "scrape_running": is_scrape_running(),
        "current_job_id": get_current_job_id(),
    }


@app.post("/api/scrape", response_model=ScrapeResponse)
async def trigger_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger a new scrape job.
    Returns immediately with job_id, scrape runs in background.
    """
    # Check if scrape is already running
    if is_scrape_running():
        running_job = get_running_scrape()
        if running_job:
            raise HTTPException(
                status_code=429,
                detail=f"Another scrape (job {running_job['id']}) is already running. Please wait.",
            )

    # Create job in database (hardcode economy/Main cabin)
    job_id = create_scrape(
        request.origin,
        request.destination,
        request.date,
        request.passengers,
        "economy",  # Always Main cabin
    )

    # Start background task
    background_tasks.add_task(
        run_scrape_job,
        job_id,
        request.origin,
        request.destination,
        request.date,
        request.passengers,
    )

    return ScrapeResponse(
        job_id=job_id,
        status="queued",
        message=f"Scrape job {job_id} queued successfully",
    )


@app.get("/api/scrapes/{job_id}", response_model=ScrapeStatus)
async def get_scrape_status(job_id: int):
    """
    Get status and results of a specific scrape job
    """
    scrape = get_scrape(job_id)

    if not scrape:
        raise HTTPException(status_code=404, detail=f"Scrape {job_id} not found")

    # Parse results JSON if available
    results = None
    if scrape["results"]:
        try:
            results = json.loads(scrape["results"])
        except (json.JSONDecodeError, TypeError):
            pass

    return ScrapeStatus(
        id=scrape["id"],
        origin=scrape["origin"],
        destination=scrape["destination"],
        date=scrape["date"],
        passengers=scrape["passengers"],
        cabin_class=scrape["cabin_class"],
        status=scrape["status"],
        started_at=scrape["started_at"],
        completed_at=scrape["completed_at"],
        results=results,
        error=scrape["error"],
        total_flights=scrape["total_flights"],
        avg_cpp=scrape["avg_cpp"],
    )


@app.get("/api/scrapes", response_model=list[ScrapeListItem])
async def list_scrapes(limit: int = 50, offset: int = 0):
    """
    List all scrapes (paginated)
    """
    scrapes = get_all_scrapes(limit, offset)

    return [
        ScrapeListItem(
            id=s["id"],
            origin=s["origin"],
            destination=s["destination"],
            date=s["date"],
            status=s["status"],
            started_at=s["started_at"],
            completed_at=s["completed_at"],
            total_flights=s["total_flights"],
            avg_cpp=s["avg_cpp"],
        )
        for s in scrapes
    ]


@app.get("/api/scrapes/latest/completed", response_model=ScrapeStatus)
async def get_latest_scrape():
    """
    Get the latest completed scrape
    """
    scrape = get_latest_completed()

    if not scrape:
        raise HTTPException(status_code=404, detail="No completed scrapes found")

    # Parse results JSON
    results = None
    if scrape["results"]:
        try:
            results = json.loads(scrape["results"])
        except (json.JSONDecodeError, TypeError):
            pass

    return ScrapeStatus(
        id=scrape["id"],
        origin=scrape["origin"],
        destination=scrape["destination"],
        date=scrape["date"],
        passengers=scrape["passengers"],
        cabin_class=scrape["cabin_class"],
        status=scrape["status"],
        started_at=scrape["started_at"],
        completed_at=scrape["completed_at"],
        results=results,
        error=scrape["error"],
        total_flights=scrape["total_flights"],
        avg_cpp=scrape["avg_cpp"],
    )


@app.delete("/api/scrapes/{job_id}")
async def delete_scrape_endpoint(job_id: int):
    """
    Delete a scrape by ID
    """
    success = delete_scrape(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Scrape {job_id} not found")

    return {"message": f"Scrape {job_id} deleted successfully"}


@app.get("/api/compare", response_model=ComparisonResponse)
async def compare_scrapes(ids: str):
    """
    Compare two scrapes side by side.
    ids parameter should be comma-separated like: ids=1,2
    """
    try:
        id_list = [int(x.strip()) for x in ids.split(",")]
        if len(id_list) != 2:
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400, detail="Invalid ids parameter. Expected format: ids=1,2"
        )

    scrape1 = get_scrape(id_list[0])
    scrape2 = get_scrape(id_list[1])

    if not scrape1:
        raise HTTPException(status_code=404, detail=f"Scrape {id_list[0]} not found")
    if not scrape2:
        raise HTTPException(status_code=404, detail=f"Scrape {id_list[1]} not found")

    # Parse results
    results1 = json.loads(scrape1["results"]) if scrape1["results"] else None
    results2 = json.loads(scrape2["results"]) if scrape2["results"] else None

    # Build status objects
    status1 = ScrapeStatus(
        id=scrape1["id"],
        origin=scrape1["origin"],
        destination=scrape1["destination"],
        date=scrape1["date"],
        passengers=scrape1["passengers"],
        cabin_class=scrape1["cabin_class"],
        status=scrape1["status"],
        started_at=scrape1["started_at"],
        completed_at=scrape1["completed_at"],
        results=results1,
        error=scrape1["error"],
        total_flights=scrape1["total_flights"],
        avg_cpp=scrape1["avg_cpp"],
    )

    status2 = ScrapeStatus(
        id=scrape2["id"],
        origin=scrape2["origin"],
        destination=scrape2["destination"],
        date=scrape2["date"],
        passengers=scrape2["passengers"],
        cabin_class=scrape2["cabin_class"],
        status=scrape2["status"],
        started_at=scrape2["started_at"],
        completed_at=scrape2["completed_at"],
        results=results2,
        error=scrape2["error"],
        total_flights=scrape2["total_flights"],
        avg_cpp=scrape2["avg_cpp"],
    )

    # Calculate comparison stats
    stats = {
        "total_flights_diff": scrape2.get("total_flights", 0)
        - scrape1.get("total_flights", 0),
        "avg_cpp_diff": round(
            (scrape2.get("avg_cpp", 0) or 0) - (scrape1.get("avg_cpp", 0) or 0), 2
        ),
    }

    # Find flights unique to each scrape
    if results1 and results2:
        flights1_set = {
            f"{f['segments'][0]['flight_number']}"
            for f in results1.get("flights", [])
            if f.get("segments")
        }
        flights2_set = {
            f"{f['segments'][0]['flight_number']}"
            for f in results2.get("flights", [])
            if f.get("segments")
        }

        stats["unique_to_scrape1"] = len(flights1_set - flights2_set)
        stats["unique_to_scrape2"] = len(flights2_set - flights1_set)
        stats["common_flights"] = len(flights1_set & flights2_set)

    return ComparisonResponse(scrape1=status1, scrape2=status2, stats=stats)


if __name__ == "__main__":
    # When run directly: python -m api.main (from src/ directory)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
