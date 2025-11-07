"""
Pydantic models for API requests and responses
"""

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    """Request to trigger a new scrape"""

    origin: str = Field(..., example="LAX")
    destination: str = Field(..., example="JFK")
    date: str = Field(..., example="2025-12-15")
    passengers: int = Field(1, ge=1, le=9)
    cabin_class: str = Field("economy", pattern="^(economy|business|first)$")


class ScrapeResponse(BaseModel):
    """Response containing scrape job ID"""

    job_id: int
    status: str
    message: str


class FlightSegment(BaseModel):
    """Single flight segment"""

    flight_number: str
    departure_time: str
    arrival_time: str


class Flight(BaseModel):
    """Flight result with pricing"""

    is_nonstop: bool
    segments: list[FlightSegment]
    total_duration: str
    points_required: int
    cash_price_usd: float
    taxes_fees_usd: float
    cpp: float


class SearchMetadata(BaseModel):
    """Search parameters"""

    origin: str
    destination: str
    date: str
    passengers: int
    cabin_class: str


class ScrapeResults(BaseModel):
    """Complete scrape results"""

    search_metadata: SearchMetadata
    flights: list[Flight]
    total_results: int


class ScrapeStatus(BaseModel):
    """Scrape job status and results"""

    id: int
    origin: str
    destination: str
    date: str
    passengers: int
    cabin_class: str
    status: str
    started_at: str
    completed_at: str | None = None
    results: ScrapeResults | None = None
    error: str | None = None
    total_flights: int | None = None
    avg_cpp: float | None = None


class ScrapeListItem(BaseModel):
    """Scrape summary for list view"""

    id: int
    origin: str
    destination: str
    date: str
    status: str
    started_at: str
    completed_at: str | None = None
    total_flights: int | None = None
    avg_cpp: float | None = None


class ComparisonResponse(BaseModel):
    """Comparison between two scrapes"""

    scrape1: ScrapeStatus
    scrape2: ScrapeStatus
    stats: dict
