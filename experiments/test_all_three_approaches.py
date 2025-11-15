"""
Comprehensive comparison: Sequential vs Pure Parallel vs Staggered Parallel
Same test suite for all 3 implementations
"""

import json
import sys
import time
from pathlib import Path

# Add src to path (now in experiments folder, go up one level)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.database import init_db
from scraper.scraper import \
    scrape_flights as scrape_parallel  # Default is pure parallel
# Import all 3 versions
from scraper.scraper_sequential import scrape_flights as scrape_sequential
from scraper.scraper_staggered import scrape_flights as scrape_staggered


def run_test_suite(scrape_func, name, description):
    """Run comprehensive test suite on a scraper function"""
    print("\n" + "=" * 70)
    print(f"TESTING: {name}")
    print(f"Description: {description}")
    print("=" * 70)

    results = {
        "name": name,
        "description": description,
        "tests_passed": 0,
        "tests_total": 0,
        "times": [],
        "cached_times": [],
        "errors": [],
    }

    # Test 1: Fresh scrape
    print(f"\n{name} - Test 1: Fresh Scrape")
    print("-" * 70)
    try:
        start = time.time()
        output = scrape_func("LAX", "JFK", "2025-12-15", 1, "economy")
        elapsed = time.time() - start
        results["times"].append(elapsed)

        flights = output.get("flights", [])
        if flights and output.get("total_results") == len(flights):
            results["tests_passed"] += 1
            print(f"✅ PASS - {elapsed:.2f}s, {len(flights)} flights")
        else:
            print("❌ FAIL - Invalid output")
            results["errors"].append("Test 1: Invalid output structure")
    except Exception as e:
        print(f"❌ FAIL - {e}")
        results["errors"].append(f"Test 1: {str(e)}")

    results["tests_total"] += 1

    # Wait between tests
    print("   Waiting 3s...")
    time.sleep(3)

    # Test 2: Cached scrape (performance test - 3 runs)
    print(f"\n{name} - Test 2: Cached Performance (3 runs)")
    print("-" * 70)

    for i in range(3):
        try:
            start = time.time()
            output = scrape_func("LAX", "JFK", "2025-12-15", 1, "economy")
            elapsed = time.time() - start
            results["times"].append(elapsed)
            results["cached_times"].append(elapsed)

            flights = output.get("flights", [])
            print(f"  Run {i+1}: {elapsed:.2f}s, {len(flights)} flights")

            if i < 2:
                time.sleep(2)
        except Exception as e:
            print(f"  Run {i+1}: ❌ FAIL - {e}")
            results["errors"].append(f"Test 2 Run {i+1}: {str(e)}")

    if len(results["cached_times"]) == 3:
        results["tests_passed"] += 1
        avg = sum(results["cached_times"]) / 3
        print(f"✅ PASS - Avg: {avg:.2f}s")
    else:
        print("❌ FAIL - Some runs failed")

    results["tests_total"] += 1

    # Calculate stats
    if results["cached_times"]:
        results["avg_cached"] = sum(results["cached_times"]) / len(
            results["cached_times"]
        )
        results["min_cached"] = min(results["cached_times"])
        results["max_cached"] = max(results["cached_times"])

    return results


def main():
    print("=" * 70)
    print("COMPREHENSIVE COMPARISON: 3 APPROACHES")
    print("=" * 70)
    print("1. Sequential: Award -> delay -> Revenue (fully sequential)")
    print("2. Pure Parallel: Award + Revenue start simultaneously")
    print("3. Staggered Parallel: Award -> delay -> Revenue (both run in parallel)")
    print()
    print("Each test: 1 fresh + 3 cached runs = ~20 API requests total")
    print("Estimated time: ~3-4 minutes")
    print()

    overall_start = time.time()

    # Clear any existing database
    db_path = Path(__file__).parent / "src" / "flights.db"
    if db_path.exists():
        db_path.unlink()
    # Reinitialize database schema
    init_db()
    print("✅ Database initialized\n")

    all_results = []

    # Test 1: Sequential
    seq_results = run_test_suite(
        scrape_sequential,
        "SEQUENTIAL",
        "Award request completes, delay, then Revenue request starts",
    )
    all_results.append(seq_results)

    print("\n⏳ Waiting 10 seconds before next test...\n")
    time.sleep(10)

    # Clear database for fresh start
    if db_path.exists():
        db_path.unlink()
    init_db()

    # Test 2: Pure Parallel
    par_results = run_test_suite(
        scrape_parallel,
        "PURE PARALLEL",
        "Award and Revenue start at exact same millisecond",
    )
    all_results.append(par_results)

    print("\n⏳ Waiting 10 seconds before next test...\n")
    time.sleep(10)

    # Clear database for fresh start
    if db_path.exists():
        db_path.unlink()
    init_db()

    # Test 3: Staggered Parallel
    stag_results = run_test_suite(
        scrape_staggered,
        "STAGGERED PARALLEL",
        "Award starts, 0.2-1.0s delay, Revenue starts (both run concurrently)",
    )
    all_results.append(stag_results)

    # Final comparison
    overall_time = time.time() - overall_start

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    print("\n📊 Test Success Rate:")
    for res in all_results:
        rate = res["tests_passed"] / res["tests_total"] * 100
        status = "✅" if rate == 100 else "⚠️"
        print(
            f"  {status} {res['name']:20s}: {res['tests_passed']}/{res['tests_total']} ({rate:.0f}%)"
        )

    print("\n⚡ Performance (cached runs - avg of 3):")
    for res in all_results:
        if res.get("avg_cached"):
            print(
                f"  {res['name']:20s}: {res['avg_cached']:.2f}s "
                f"(range: {res['min_cached']:.2f}s - {res['max_cached']:.2f}s)"
            )

    # Find fastest
    if all(res.get("avg_cached") for res in all_results):
        fastest = min(all_results, key=lambda x: x["avg_cached"])
        slowest = max(all_results, key=lambda x: x["avg_cached"])
        diff = slowest["avg_cached"] - fastest["avg_cached"]

        print(f"\n  🏆 Fastest: {fastest['name']} ({fastest['avg_cached']:.2f}s)")
        print(f"  🐌 Slowest: {slowest['name']} ({slowest['avg_cached']:.2f}s)")
        print(
            f"  📊 Difference: {diff:.2f}s ({diff/slowest['avg_cached']*100:.1f}% faster)"
        )

    print("\n🚨 Errors & Reliability:")
    for res in all_results:
        if res["errors"]:
            print(f"  ❌ {res['name']:20s}: {len(res['errors'])} errors")
            for err in res["errors"][:3]:  # Show first 3
                print(f"     - {err}")
        else:
            print(f"  ✅ {res['name']:20s}: No errors")

    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    # Find most reliable
    best_reliability = max(
        all_results, key=lambda x: x["tests_passed"] / x["tests_total"]
    )

    # Check if all are equally reliable
    all_reliable = all(res["tests_passed"] == res["tests_total"] for res in all_results)

    if all_reliable and all(res.get("avg_cached") for res in all_results):
        fastest = min(all_results, key=lambda x: x["avg_cached"])
        sequential = next(r for r in all_results if r["name"] == "SEQUENTIAL")

        speed_diff = sequential["avg_cached"] - fastest["avg_cached"]

        print("✅ All approaches are 100% reliable!")
        print("\nSpeed comparison:")
        print(f"  • Sequential: {sequential['avg_cached']:.2f}s")
        print(f"  • Fastest ({fastest['name']}): {fastest['avg_cached']:.2f}s")
        print(
            f"  • Difference: {speed_diff:.2f}s ({speed_diff/sequential['avg_cached']*100:.1f}%)"
        )

        if speed_diff < 0.5:
            print("\n🎯 RECOMMENDATION: **SEQUENTIAL**")
            print("   Reasons:")
            print(f"   • Only {abs(speed_diff):.2f}s slower (negligible)")
            print("   • Most human-like (requests don't overlap)")
            print("   • Lowest bot detection risk")
            print("   • Contest emphasizes 'without detection'")
        elif speed_diff < 1.5:
            print(
                "\n⚖️  RECOMMENDATION: **SEQUENTIAL** (safer) or **STAGGERED** (faster)"
            )
            print("   Trade-off decision:")
            print(f"   • Sequential: Safest, only {speed_diff:.2f}s slower")
            print(f"   • Staggered: {speed_diff:.2f}s faster, medium bot risk")
        else:
            staggered = next(
                (r for r in all_results if r["name"] == "STAGGERED PARALLEL"), None
            )
            if staggered:
                stag_diff = sequential["avg_cached"] - staggered["avg_cached"]
                print("\n⚖️  RECOMMENDATION: **STAGGERED PARALLEL**")
                print(f"   • {stag_diff:.2f}s faster than sequential")
                print("   • Lower bot risk than pure parallel")
                print("   • Good speed/safety balance")
    else:
        # Some failed - recommend most reliable
        print("⚠️  Not all approaches are reliable!")
        print(f"\n🎯 RECOMMENDATION: **{best_reliability['name']}**")
        print(
            f"   • Highest success rate: {best_reliability['tests_passed']}/{best_reliability['tests_total']}"
        )
        print("   • Reliability is more important than speed")

    print(f"\n⏱️  Total test time: {overall_time/60:.1f} minutes")

    # Write results to JSON
    comparison_data = {
        "results": all_results,
        "total_time_seconds": overall_time,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open("comparison_results.json", "w") as f:
        json.dump(comparison_data, f, indent=2)
    print("📊 Detailed results saved to: comparison_results.json")


if __name__ == "__main__":
    main()
