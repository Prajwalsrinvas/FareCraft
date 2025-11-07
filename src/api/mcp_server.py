"""
MCP Server for FareCraft - Exposes flight scraping as an MCP tool

This module can be run in two modes:
1. Imported by main.py for HTTP transport (localhost:8000/mcp)
2. Run directly for STDIO transport (Claude Desktop)
"""

from fastmcp import FastMCP
from pydantic import Field

from scraper.scraper import scrape_flights

# Create MCP server
mcp = FastMCP("FareCraft")


@mcp.tool()
def scrape_aa_flights(
    origin: str = Field(
        description="Three-letter IATA airport code for departure (e.g., 'LAX')",
        pattern="^[A-Z]{3}$",
    ),
    destination: str = Field(
        description="Three-letter IATA airport code for arrival (e.g., 'JFK')",
        pattern="^[A-Z]{3}$",
    ),
    date: str = Field(
        description="Flight date in YYYY-MM-DD format (e.g., '2025-12-15')",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
    ),
    passengers: int = Field(
        description="Number of passengers (1-9)",
        ge=1,
        le=9,
    ),
) -> dict:
    """
    Scrape American Airlines flights and calculate CPP (Cents Per Point) for award redemptions.

    This tool scrapes both cash prices and award pricing for Main Cabin (economy) flights,
    then calculates the value you get per point (CPP) for each flight.

    Returns flight data including:
    - Flight numbers and times
    - Cash prices and award points required
    - Taxes/fees
    - CPP (Cents Per Point) calculation
    - Whether flights are nonstop or have connections

    Note: This process takes 30-60 seconds as it bypasses anti-bot protection.
    """
    # Call the scraper directly (no database storage)
    results = scrape_flights(
        origin=origin.upper(),
        destination=destination.upper(),
        date=date,
        passengers=passengers,
        cabin_class="economy",  # Always Main cabin as per contest requirements
    )

    return results


# Allow running directly for STDIO transport (Claude Desktop)
if __name__ == "__main__":
    mcp.run()
