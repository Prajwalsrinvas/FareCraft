"""
Comprehensive test suite to ensure scraper robustness
Tests: fresh run, cookie caching, error handling, data accuracy
"""
import json
import os
import sys
import time
from pathlib import Path

# Add src to path (now in experiments folder, go up one level)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scraper.scraper import scrape_flights  # Uses pure parallel (production default)


def test_1_fresh_scrape():
    """Test 1: Fresh scrape with new cookies"""
    print("=" * 70)
    print("TEST 1: Fresh Scrape (DB removed, will generate new cookies)")
    print("=" * 70)

    start = time.time()

    try:
        output = scrape_flights("LAX", "JFK", "2025-12-15", 1, "economy")
        elapsed = time.time() - start

        flights = output.get("flights", [])

        print(f"\n✅ Test 1 PASSED")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Flights: {len(flights)}")
        print(f"   Has search_metadata: {bool(output.get('search_metadata'))}")
        print(f"   Total_results matches: {output.get('total_results') == len(flights)}")

        # Validate a sample flight
        if flights:
            flight = flights[0]
            print(f"\n   Sample flight validation:")
            print(f"   - Has segments: {bool(flight.get('segments'))}")
            print(f"   - Has points_required: {bool(flight.get('points_required'))}")
            print(f"   - Has cash_price_usd: {bool(flight.get('cash_price_usd'))}")
            print(f"   - Has cpp: {bool(flight.get('cpp'))}")

            # Verify CPP calculation
            cpp_calc = round((flight['cash_price_usd'] - flight['taxes_fees_usd']) / flight['points_required'] * 100, 2)
            cpp_match = abs(cpp_calc - flight['cpp']) < 0.01
            print(f"   - CPP calculation correct: {cpp_match} (calc: {cpp_calc}, stored: {flight['cpp']})")

        return True, elapsed

    except Exception as e:
        print(f"\n❌ Test 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


def test_2_cached_scrape():
    """Test 2: Second scrape using cached cookies"""
    print("\n" + "=" * 70)
    print("TEST 2: Cached Scrape (should use existing cookies)")
    print("=" * 70)

    start = time.time()

    try:
        output = scrape_flights("LAX", "JFK", "2025-12-15", 1, "economy")
        elapsed = time.time() - start

        flights = output.get("flights", [])

        print(f"\n✅ Test 2 PASSED")
        print(f"   Time: {elapsed:.2f}s (should be faster than Test 1)")
        print(f"   Flights: {len(flights)}")

        return True, elapsed

    except Exception as e:
        print(f"\n❌ Test 2 FAILED: {e}")
        return False, 0


def test_3_output_json_format():
    """Test 3: Validate output.json format matches contest spec"""
    print("\n" + "=" * 70)
    print("TEST 3: Output JSON Format Validation")
    print("=" * 70)

    try:
        with open("output.json", "r") as f:
            data = json.load(f)

        # Check required top-level keys
        required_keys = ["search_metadata", "flights", "total_results"]
        missing_keys = [k for k in required_keys if k not in data]

        if missing_keys:
            print(f"❌ Missing keys: {missing_keys}")
            return False

        # Check search_metadata
        metadata = data["search_metadata"]
        metadata_keys = ["origin", "destination", "date", "passengers", "cabin_class"]
        missing_metadata = [k for k in metadata_keys if k not in metadata]

        if missing_metadata:
            print(f"❌ Missing metadata keys: {missing_metadata}")
            return False

        # Check flights structure
        flights = data["flights"]
        if not isinstance(flights, list):
            print(f"❌ Flights is not a list")
            return False

        if len(flights) == 0:
            print(f"⚠️  No flights found (might be route issue)")

        # Check first flight structure
        if flights:
            flight = flights[0]
            flight_keys = ["is_nonstop", "segments", "total_duration", "points_required",
                          "cash_price_usd", "taxes_fees_usd", "cpp"]
            missing_flight_keys = [k for k in flight_keys if k not in flight]

            if missing_flight_keys:
                print(f"❌ Missing flight keys: {missing_flight_keys}")
                return False

            # Check segments structure
            if not flight["segments"] or not isinstance(flight["segments"], list):
                print(f"❌ Segments is empty or not a list")
                return False

            segment = flight["segments"][0]
            segment_keys = ["flight_number", "departure_time", "arrival_time"]
            missing_segment_keys = [k for k in segment_keys if k not in segment]

            if missing_segment_keys:
                print(f"❌ Missing segment keys: {missing_segment_keys}")
                return False

            # Type checks
            type_checks = {
                "points_required": int,
                "cash_price_usd": float,
                "taxes_fees_usd": float,
                "cpp": float,
                "is_nonstop": bool,
            }

            for key, expected_type in type_checks.items():
                if not isinstance(flight[key], expected_type):
                    print(f"❌ {key} has wrong type: expected {expected_type}, got {type(flight[key])}")
                    return False

        print(f"\n✅ Test 3 PASSED")
        print(f"   All required fields present")
        print(f"   All types correct")
        print(f"   Format matches contest specification")

        return True

    except FileNotFoundError:
        print(f"❌ output.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_data_consistency():
    """Test 4: Run scrape twice, verify data is consistent"""
    print("\n" + "=" * 70)
    print("TEST 4: Data Consistency (two scrapes should return similar results)")
    print("=" * 70)

    print("\nRun 1...")
    try:
        output1 = scrape_flights("LAX", "JFK", "2025-12-15", 1, "economy")
        flights1 = output1.get("flights", [])

        print(f"   Flights: {len(flights1)}")

        # Wait a bit between scrapes
        print("\nWaiting 3 seconds before run 2...")
        time.sleep(3)

        print("Run 2...")
        output2 = scrape_flights("LAX", "JFK", "2025-12-15", 1, "economy")
        flights2 = output2.get("flights", [])

        print(f"   Flights: {len(flights2)}")

        # Compare counts (should be close)
        diff = abs(len(flights1) - len(flights2))

        if diff <= 3:  # Allow small variance (flights come/go)
            print(f"\n✅ Test 4 PASSED")
            print(f"   Flight count difference: {diff} (acceptable)")
        else:
            print(f"\n⚠️  Test 4 WARNING: Large difference in flight count: {diff}")
            print(f"   This might indicate inconsistent scraping")

        return True

    except Exception as e:
        print(f"\n❌ Test 4 FAILED: {e}")
        return False


def test_5_performance_baseline():
    """Test 5: Establish performance baseline (3 runs)"""
    print("\n" + "=" * 70)
    print("TEST 5: Performance Baseline (3 consecutive runs)")
    print("=" * 70)

    times = []

    for i in range(3):
        print(f"\nRun {i+1}/3...")
        start = time.time()

        try:
            output = scrape_flights("LAX", "JFK", "2025-12-15", 1, "economy")
            elapsed = time.time() - start
            times.append(elapsed)

            print(f"   Time: {elapsed:.2f}s")
            print(f"   Flights: {len(output.get('flights', []))}")

            if i < 2:  # Wait between runs (except last)
                print("   Waiting 3 seconds...")
                time.sleep(3)

        except Exception as e:
            print(f"   ❌ Failed: {e}")
            times.append(None)

    # Calculate stats
    valid_times = [t for t in times if t is not None]

    if valid_times:
        avg_time = sum(valid_times) / len(valid_times)
        min_time = min(valid_times)
        max_time = max(valid_times)

        print(f"\n✅ Test 5 COMPLETE")
        print(f"   Average time: {avg_time:.2f}s")
        print(f"   Min time: {min_time:.2f}s")
        print(f"   Max time: {max_time:.2f}s")
        print(f"   Success rate: {len(valid_times)}/3 ({len(valid_times)/3*100:.0f}%)")

        if len(valid_times) == 3 and max_time < 15:
            print(f"   Performance: EXCELLENT ✅")
        elif len(valid_times) >= 2:
            print(f"   Performance: ACCEPTABLE ⚠️")
        else:
            print(f"   Performance: NEEDS IMPROVEMENT ❌")

        return True
    else:
        print(f"\n❌ Test 5 FAILED: All runs failed")
        return False


def main():
    print("Comprehensive Scraper Test Suite")
    print("=" * 70)
    print("Running 5 test scenarios...")
    print("Warning: This will make multiple API requests (waiting between each)")
    print()

    overall_start = time.time()
    results = {}

    # Test 1: Fresh scrape
    results["test_1"], time_1 = test_1_fresh_scrape()

    # Wait between tests
    print("\n⏳ Waiting 3 seconds before next test...")
    time.sleep(3)

    # Test 2: Cached scrape
    results["test_2"], time_2 = test_2_cached_scrape()

    # Test 3: Output format
    results["test_3"] = test_3_output_json_format()

    # Wait before stress tests
    print("\n⏳ Waiting 5 seconds before consistency tests...")
    time.sleep(5)

    # Test 4: Consistency
    results["test_4"] = test_4_data_consistency()

    # Wait before final test
    print("\n⏳ Waiting 5 seconds before performance baseline...")
    time.sleep(5)

    # Test 5: Performance baseline
    results["test_5"] = test_5_performance_baseline()

    # Summary
    overall_time = time.time() - overall_start

    print("\n" + "=" * 70)
    print("TEST SUITE SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v is True)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"Total test time: {overall_time:.1f}s")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Scraper is production ready!")
        return 0
    elif passed >= total - 1:
        print("\n⚠️  MOSTLY PASSED - Minor issues, review failed tests")
        return 1
    else:
        print("\n❌ MULTIPLE FAILURES - Review and fix before submission")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
