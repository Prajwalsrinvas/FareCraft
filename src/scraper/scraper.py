"""
Refactored American Airlines Flight Scraper Module
Hybrid approach: Camoufox (Firefox) for cookie generation → curl_cffi for fast API requests
"""

import concurrent.futures
import threading
import time
from datetime import datetime
from typing import Any

from camoufox.sync_api import Camoufox
from curl_cffi import requests


# Debug logging
def log_debug(message: str) -> None:
    """Enhanced debug logging with thread info"""
    thread_id: int | None = threading.current_thread().ident
    thread_name: str = threading.current_thread().name
    timestamp: str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [Thread-{thread_id}:{thread_name}] {message}")


def get_akamai_cookies() -> dict[str, str]:
    """
    Generate valid Akamai cookies using Camoufox (stealth Firefox).
    Returns dictionary of cookie name:value pairs.
    """
    log_debug("🦊 START: Launching Camoufox to bypass Akamai Bot Manager...")
    cookie_gen_start = time.time()

    with Camoufox(headless=True) as browser:
        page = browser.new_page()

        # Visit booking search page to trigger ALL required cookies
        # Why: Booking page generates MORE cookies than homepage (spa_session_id, dtPC)
        #      which are validated by API endpoints to detect bots
        # This generates: _abck, spa_session_id, dtPC, and other tracking cookies
        log_debug("🌐 Loading aa.com booking search page...")
        search_url = "https://www.aa.com/booking/search?locale=en_US&fareType=Lowest&pax=1&adult=1&type=OneWay&searchType=Revenue&cabin=&carriers=ALL&travelType=personal&slices=%5B%7B%22orig%22:%22LAX%22,%22origNearby%22:false,%22dest%22:%22JFK%22,%22destNearby%22:false,%22date%22:%222025-12-15%22%7D%5D"
        page.goto(search_url, wait_until="networkidle")

        # Wait for Akamai sensor to execute and generate cookies
        # Why: Akamai Bot Manager sensor takes 8-12 seconds to complete fingerprinting
        #      Rushing this results in untrusted cookies (~0~ instead of ~-1~)
        log_debug("⏳ Waiting for Akamai sensor (10s)...")
        time.sleep(10)

        # Simulate human behavior to ensure sensor completion
        # Why: Mouse movements and scrolling help Akamai's behavioral analysis
        #      recognize this as a real browser, not a bot
        page.mouse.move(100, 100)
        time.sleep(0.5)  # Natural pause between movements
        page.mouse.move(300, 200)
        time.sleep(0.5)
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(2)  # Longer pause after scroll for realism

        # Extract all cookies
        cookies = browser.contexts[0].cookies()

    cookie_dict = {c["name"]: c["value"] for c in cookies}
    cookie_gen_time = time.time() - cookie_gen_start

    # Verify critical Akamai cookies
    abck = cookie_dict.get("_abck", "")
    abck_preview = abck[:50] + "..." if len(abck) > 50 else abck

    if "~-1~" in abck:
        log_debug(f"✅ Akamai cookies generated successfully in {cookie_gen_time:.2f}s")
        log_debug(f"   Total cookies: {len(cookie_dict)}")
        log_debug(f"   _abck preview: {abck_preview}")
        log_debug(
            f"   XSRF-TOKEN: {'Present' if 'XSRF-TOKEN' in cookie_dict else 'MISSING'}"
        )
    else:
        log_debug("⚠️  WARNING: _abck cookie may not be fully trusted!")
        log_debug(f"   _abck value: {abck_preview}")

    return cookie_dict


def fetch_flights(
    cookies: dict[str, str],
    search_type: str,
    origin: str,
    destination: str,
    date: str,
    passengers: int,
) -> list[dict]:
    """
    Fetch flight data using curl_cffi with Camoufox-generated cookies.

    Args:
        cookies: Dictionary of cookies from Camoufox
        search_type: 'Award' for miles/points, 'Revenue' for cash prices
        origin: Origin airport code
        destination: Destination airport code
        date: Departure date (YYYY-MM-DD)
        passengers: Number of passengers

    Returns:
        List of flight objects
    """
    log_debug(f"🚀 START: Fetching {search_type} pricing for {origin}->{destination}")
    fetch_start = time.time()

    try:
        # Create session with Firefox impersonation to match Camoufox
        # Why: Must match Camoufox's Firefox version to avoid fingerprint inconsistencies
        #      AA.com compares TLS fingerprint with User-Agent; mismatches = bot detection
        log_debug("   Creating curl_cffi Session with firefox133 impersonation...")
        session = requests.Session(impersonate="firefox133")
        log_debug("   ✓ Session created successfully")

        # Inject all cookies from Camoufox
        log_debug(f"   Injecting {len(cookies)} cookies into session...")
        abck_in_cookies = "_abck" in cookies
        for name, value in cookies.items():
            session.cookies.set(name, value, domain="aa.com")
        log_debug(f"   ✓ Cookies injected (_abck present: {abck_in_cookies})")

        # Headers matching Firefox
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.aa.com",
            "referer": "https://www.aa.com/booking/choose-flights/1",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "x-xsrf-token": cookies.get("XSRF-TOKEN", ""),
            # Dynamic headers from cookies (critical for bot detection)
            # Why: AA.com validates these headers match cookie values server-side
            #      Missing/mismatched values trigger immediate 403 Forbidden
            "x-cid": cookies.get("spa_session_id", ""),  # Session correlation ID
            "x-dtpc": cookies.get("dtPC", ""),  # Dynatrace performance cookie
        }

        # API payload
        payload = {
            "metadata": {
                "selectedProducts": [],
                "tripType": "OneWay",
                "udo": {},
            },
            "passengers": [{"type": "adult", "count": passengers}],
            "requestHeader": {"clientId": "AAcom"},
            "slices": [
                {
                    "allCarriers": True,
                    "cabin": "",
                    "departureDate": date,
                    "destination": destination,
                    "destinationNearbyAirports": False,
                    "maxStops": None,
                    "origin": origin,
                    "originNearbyAirports": False,
                }
            ],
            "tripOptions": {
                "corporateBooking": False,
                "fareType": "Lowest",
                "locale": "en_US",
                "pointOfSale": None,
                "searchType": search_type,
            },
            "loyaltyInfo": None,
            "version": "cfr",
            "queryParams": {
                "sliceIndex": 0,
                "sessionId": "",
                "solutionSet": "",
                "solutionId": "",
                "sort": "CARRIER",
            },
        }

        log_debug("   Sending POST request to AA API...")
        request_start = time.time()

        response = session.post(
            "https://www.aa.com/booking/api/search/itinerary",
            headers=headers,
            json=payload,
            timeout=30,
        )

        request_time = time.time() - request_start
        log_debug(f"   ✓ Response received in {request_time:.2f}s")
        log_debug(f"   Response status: {response.status_code}")

        if response.status_code != 200:
            log_debug(f"   ❌ ERROR: Non-200 status code: {response.status_code}")
            log_debug(f"   Response headers: {dict(response.headers)}")
            try:
                response_text = response.text[:500]
                log_debug(f"   Response body preview: {response_text}")
            except Exception:
                pass
            raise Exception(
                f"{search_type} request failed with status {response.status_code}"
            )

        data = response.json()
        flights = data.get("slices", [])

        total_time = time.time() - fetch_start
        log_debug(
            f"✅ SUCCESS: {search_type} completed in {total_time:.2f}s - {len(flights)} flights retrieved"
        )

        return flights

    except Exception as e:
        total_time = time.time() - fetch_start
        log_debug(f"❌ EXCEPTION in fetch_flights after {total_time:.2f}s:")
        log_debug(f"   Exception type: {type(e).__name__}")
        log_debug(f"   Exception message: {str(e)}")
        import traceback

        log_debug(f"   Traceback: {traceback.format_exc()}")
        raise


def extract_main_cabin_award(flight: dict) -> tuple[int | None, float | None]:
    """Extract Main cabin pricing from Award flight."""
    for product in flight.get("productPricing", []):
        regular_price = product.get("regularPrice", {})
        fares = regular_price.get("fares", [])

        if fares and len(fares) > 0:
            brand_code = fares[0].get("brandInfo", {}).get("brandCode")
            if brand_code == "MAIN":
                points = regular_price.get("perPassengerAwardPoints")
                taxes = regular_price.get("perPassengerTaxesAndFees", {}).get("amount")
                return points, taxes

    return None, None


def extract_main_cabin_cash(flight: dict) -> tuple[float | None, float | None]:
    """Extract Main cabin pricing from Revenue flight."""
    product_groups = flight.get("productGroups", {})
    main_products = product_groups.get("MAIN", [])

    for product in main_products:
        fares = product.get("fares", [])

        if fares and len(fares) > 0:
            brand_code = fares[0].get("brandInfo", {}).get("brandCode")
            if brand_code == "MAIN":
                slice_pricing = product.get("slicePricing", {})
                total = slice_pricing.get("allPassengerDisplayTotal", {}).get("amount")
                taxes = slice_pricing.get("allPassengerDisplayTaxTotal", {}).get(
                    "amount"
                )
                return total, taxes

    return None, None


def extract_flight_details(flight: dict) -> dict:
    """Extract flight number, times, duration, etc."""
    segments = []

    for segment in flight.get("segments", []):
        flight_info = segment.get("flight", {})
        flight_number = (
            f"{flight_info.get('carrierCode', '')}{flight_info.get('flightNumber', '')}"
        )

        legs = segment.get("legs", [])
        if legs:
            departure_dt = legs[0].get("departureDateTime", "")
            arrival_dt = legs[-1].get("arrivalDateTime", "")

            try:
                dep_time = datetime.fromisoformat(
                    departure_dt.replace("Z", "+00:00")
                ).strftime("%H:%M")
                arr_time = datetime.fromisoformat(
                    arrival_dt.replace("Z", "+00:00")
                ).strftime("%H:%M")
            except (ValueError, AttributeError):
                dep_time = departure_dt
                arr_time = arrival_dt

            segments.append(
                {
                    "flight_number": flight_number,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                }
            )

    # Duration
    duration_min = flight.get("durationInMinutes", 0)
    hours = duration_min // 60
    minutes = duration_min % 60
    total_duration = f"{hours}h {minutes}m"

    # Nonstop check
    is_nonstop = flight.get("stops", 0) == 0

    return {
        "is_nonstop": is_nonstop,
        "segments": segments,
        "total_duration": total_duration,
    }


def calculate_cpp(cash_price: float, taxes: float, points: int) -> float:
    """Calculate Cents Per Point: (cash_price - taxes) / points * 100"""
    if points == 0:
        return 0
    return round((cash_price - taxes) / points * 100, 2)


def match_and_process_flights(
    award_flights: list[dict], cash_flights: list[dict]
) -> list[dict]:
    """
    Match Award and Cash flights by hash, extract Main cabin pricing, calculate CPP.
    Returns list of processed flights ready for JSON output.
    """
    log_debug(
        f"🔍 Matching {len(award_flights)} award flights with {len(cash_flights)} cash flights..."
    )

    # Build hash maps
    award_map = {f.get("hash"): f for f in award_flights if f.get("hash")}
    cash_map = {f.get("hash"): f for f in cash_flights if f.get("hash")}

    # Find common hashes
    common_hashes = set(award_map.keys()) & set(cash_map.keys())
    log_debug(f"   Found {len(common_hashes)} matching hashes")

    results = []
    skipped = 0

    for hash_key in common_hashes:
        award_flight = award_map[hash_key]
        cash_flight = cash_map[hash_key]

        # Extract Main cabin pricing
        points, award_taxes = extract_main_cabin_award(award_flight)
        cash_price, cash_taxes = extract_main_cabin_cash(cash_flight)

        # Skip if Main cabin not available
        if points is None or cash_price is None:
            skipped += 1
            continue

        # Use taxes from award response (preferred for CPP calculation)
        # Why: Award booking taxes are more accurate since they're what you actually pay
        #      when redeeming points. Cash taxes can sometimes differ slightly.
        taxes = award_taxes if award_taxes is not None else cash_taxes

        # Extract flight details
        details = extract_flight_details(award_flight)

        # Calculate CPP
        cpp = calculate_cpp(cash_price, taxes, points)

        # Build output object
        flight_obj = {
            "is_nonstop": details["is_nonstop"],
            "segments": details["segments"],
            "total_duration": details["total_duration"],
            "points_required": int(points),
            "cash_price_usd": float(cash_price),
            "taxes_fees_usd": float(taxes) if taxes else 0,
            "cpp": cpp,
        }

        results.append(flight_obj)

    log_debug(
        f"✅ Processed {len(results)} flights with Main cabin pricing (skipped {skipped} without Main)"
    )
    return results


def scrape_flights(
    origin: str, destination: str, date: str, passengers: int, cabin_class: str
) -> dict[str, Any]:
    """
    Main scraping function that orchestrates the entire process.

    Args:
        origin: Origin airport code (e.g., "LAX")
        destination: Destination airport code (e.g., "JFK")
        date: Departure date in YYYY-MM-DD format
        passengers: Number of passengers
        cabin_class: Cabin class (economy, business, first)

    Returns:
        Dictionary with search_metadata, flights, and total_results
    """
    log_debug("=" * 70)
    log_debug(f"SCRAPE START: {origin} → {destination} on {date}")
    log_debug("=" * 70)
    overall_start = time.time()

    # Step 1: Generate Akamai cookies
    log_debug("STEP 1: Generate Akamai cookies")
    cookies = get_akamai_cookies()
    cookie_time = time.time() - overall_start
    log_debug(f"STEP 1 COMPLETE: Cookies generated in {cookie_time:.2f}s")

    # Step 2: Fetch Award and Revenue data concurrently
    log_debug("STEP 2: Fetch flight data from AA.com API (concurrent)")
    log_debug(f"   Time since cookie generation: {time.time() - overall_start:.2f}s")

    api_start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        log_debug("   Submitting Award and Revenue tasks to ThreadPoolExecutor...")
        award_future = executor.submit(
            fetch_flights, cookies, "Award", origin, destination, date, passengers
        )
        cash_future = executor.submit(
            fetch_flights, cookies, "Revenue", origin, destination, date, passengers
        )

        log_debug("   Waiting for futures to complete...")
        award_flights = award_future.result()
        cash_flights = cash_future.result()

    api_time = time.time() - api_start
    log_debug(f"STEP 2 COMPLETE: Both API calls completed in {api_time:.2f}s")

    # Step 3: Match flights and extract Main cabin pricing
    log_debug("STEP 3: Match flights and extract Main cabin pricing")
    matched_flights = match_and_process_flights(award_flights, cash_flights)
    log_debug(f"STEP 3 COMPLETE: Matched {len(matched_flights)} flights")

    # Step 4: Build output
    output = {
        "search_metadata": {
            "origin": origin,
            "destination": destination,
            "date": date,
            "passengers": passengers,
            "cabin_class": cabin_class,
        },
        "flights": matched_flights,
        "total_results": len(matched_flights),
    }

    total_time = time.time() - overall_start
    log_debug("=" * 70)
    log_debug(
        f"✅ SCRAPE COMPLETE in {total_time:.2f}s! Found {len(matched_flights)} flights"
    )
    log_debug("=" * 70)

    return output
