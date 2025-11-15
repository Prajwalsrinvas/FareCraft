#!/usr/bin/env python3
"""
FareCraft Performance Test Suite - 50 Consecutive Runs

This script tests the FareCraft scraper's performance and reliability by running
50 consecutive scrapes using the production Docker image from Docker Hub.

Test Methodology:
- Uses public Docker image: prajwalsrinivas7/farecraft
- Preserves cookie cache across runs (real-world scenario)
- Runs back-to-back for maximum stress testing
- Tracks timing, success rate, retry attempts, and errors
- Generates comprehensive statistics for evaluation
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not available - graphs will be skipped")


class TestRunner:
    def __init__(self, num_runs: int = 50):
        self.num_runs = num_runs
        self.docker_image = "prajwalsrinivas7/farecraft"
        self.output_dir = Path("./output")
        self.results = []
        self.start_time = None
        self.end_time = None

    def setup(self):
        """Pre-test setup: pull Docker image and verify environment"""
        print("=" * 80)
        print("FareCraft Performance Test Suite")
        print("=" * 80)
        print("Test Configuration:")
        print(f"  • Runs: {self.num_runs}")
        print(f"  • Docker Image: {self.docker_image}")
        print(
            "  • Cache Strategy: Cold start (cleared before test), preserved during test"
        )
        print("  • Execution: Back-to-back (no delays)")
        print("  • Route: LAX → JFK (2025-12-15)")
        print()

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)

        # Clear cookie cache for unbiased cold-start test
        # This ensures Run #1 generates fresh cookies, measuring true first-run performance
        cache_file = self.output_dir / "flights.db"
        if cache_file.exists():
            print("🧹 Clearing cookie cache (ensures cold-start test)")
            cache_file.unlink()
            print("   Run #1 will generate fresh cookies\n")

        # Pull Docker image (not counted in test time)
        print("📦 Pulling Docker image (not included in test timing)...")
        try:
            result = subprocess.run(
                ["docker", "pull", self.docker_image],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                print(f"❌ Failed to pull Docker image: {result.stderr}")
                sys.exit(1)
            print("✅ Docker image pulled successfully\n")
        except subprocess.TimeoutExpired:
            print("❌ Docker pull timed out (5 minutes)")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ Docker not found. Please install Docker first.")
            sys.exit(1)

        # Verify log directory will be created
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Clear old test logs (but keep cookie cache!)
        # This ensures we start with a clean log file for accurate per-run parsing
        old_log = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        if old_log.exists():
            print(f"🧹 Clearing old test logs: {old_log.name}")
            old_log.unlink()

        print(f"📁 Output directory: {self.output_dir.absolute()}")
        print("📊 Results will be saved to: test_results.json")
        print("📄 Human-readable report: test_report.txt\n")

    def run_single_test(self, run_number: int) -> dict[str, Any]:
        """Run a single scrape and collect metrics"""
        print(f"\n{'─' * 80}")
        print(f"Run #{run_number}/{self.num_runs}")
        print(f"{'─' * 80}")

        # Track log file size BEFORE run (to read only new logs)
        log_file = (
            self.output_dir / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        )
        log_size_before = log_file.stat().st_size if log_file.exists() else 0

        # Start timing
        start_time = time.time()

        # Run Docker container
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.output_dir.absolute()}:/app/output",
            self.docker_image,
            "python",
            "scraper/scraper.py",
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 minute timeout (allows 3 cookie attempts + API retries)
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"⏱️  Time: {elapsed:.2f}s")
            print("❌ TIMEOUT (>180s)")
            return {
                "run": run_number,
                "success": False,
                "time": elapsed,
                "exit_code": -1,
                "error": "Timeout after 180 seconds",
                "flights": 0,
                "retries_detected": False,
                "used_cache": False,
            }

        # Stop timing
        elapsed = time.time() - start_time

        # Read output.json
        output_file = self.output_dir / "output.json"
        flights = []
        parse_error = None

        if output_file.exists():
            try:
                with open(output_file, "r") as f:
                    data = json.load(f)
                    flights = data.get("flights", [])
                    # Check if there's an error field
                    if "error" in data:
                        parse_error = data["error"]
            except json.JSONDecodeError as e:
                parse_error = f"Invalid JSON: {e}"
            except Exception as e:
                parse_error = f"Failed to read output: {e}"
        else:
            parse_error = "output.json not found"

        # Determine success
        success = exit_code == 0 and parse_error is None and len(flights) > 0

        # Analyze logs for retries and cache usage
        # Read ONLY logs from THIS run (from log_size_before to current size)
        retries_detected = False
        used_cache = False
        retry_details = []

        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    # Seek to where logs started for THIS run
                    f.seek(log_size_before)
                    # Read only new content (this run's logs)
                    run_logs = f.read()

                # Detect cookie cache usage
                if "✅ Using cached cookies" in run_logs:
                    used_cache = True
                elif "🆕 No cached cookies found" in run_logs:
                    used_cache = False
                elif "🔄 Cookies expire in" in run_logs:
                    used_cache = False  # Cache expired, fetching fresh

                # Detect retries at cookie level
                if (
                    "⚠️  Cookie attempt 2" in run_logs
                    or "Cookie attempt 1 failed" in run_logs
                ):
                    retries_detected = True
                    retry_details.append("Cookie retry (attempt 2)")
                if "⚠️  Cookie attempt 3" in run_logs:
                    retries_detected = True
                    retry_details.append("Cookie retry (attempt 3)")

                # Detect retries at API level (count occurrences, not just presence)
                forbidden_count = run_logs.count("⚠️  Forbidden (403)")
                rate_limit_count = run_logs.count("⚠️  Rate limited (429)")
                server_error_count = run_logs.count("⚠️  Server error")

                if forbidden_count > 0:
                    retries_detected = True
                    retry_details.append(f"Forbidden 403 ({forbidden_count}x)")
                if rate_limit_count > 0:
                    retries_detected = True
                    retry_details.append(f"Rate limited 429 ({rate_limit_count}x)")
                if server_error_count > 0:
                    retries_detected = True
                    retry_details.append(f"Server error 5xx ({server_error_count}x)")

            except Exception as e:
                print(f"⚠️  Warning: Could not parse logs: {e}")

        # Print summary
        print(f"⏱️  Time: {elapsed:.2f}s")
        print(f"🔄 Cache: {'✅ Used' if used_cache else '❌ Fresh cookies'}")
        print(f"✈️  Flights: {len(flights)}")
        print(f"📊 Exit Code: {exit_code}")

        if retries_detected:
            print(f"🔁 Retries: {', '.join(retry_details)}")

        if success:
            print("✅ SUCCESS")
        else:
            print(f"❌ FAILED: {parse_error or 'Unknown error'}")

        # Return results
        return {
            "run": run_number,
            "success": success,
            "time": elapsed,
            "exit_code": exit_code,
            "error": parse_error or (stderr if not success else None),
            "flights": len(flights),
            "retries_detected": retries_detected,
            "retry_details": retry_details if retries_detected else [],
            "used_cache": used_cache,
            "stdout_preview": stdout[-500:] if stdout else "",  # Last 500 chars
        }

    def run_all_tests(self):
        """Run all test iterations"""
        print("\n" + "=" * 80)
        print("STARTING TEST SUITE")
        print("=" * 80)

        self.start_time = time.time()

        for i in range(1, self.num_runs + 1):
            result = self.run_single_test(i)
            self.results.append(result)

            # Print progress
            successes = sum(1 for r in self.results if r["success"])
            print(
                f"\n📈 Progress: {i}/{self.num_runs} ({successes}/{i} successful, {successes/i*100:.1f}%)"
            )

        self.end_time = time.time()

    def calculate_statistics(self) -> dict[str, Any]:
        """Calculate comprehensive statistics from test results"""
        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        # Timing statistics (successful runs only)
        times = [r["time"] for r in successful] if successful else []

        # Separate first run vs cached runs
        first_run = self.results[0] if self.results else None
        cached_runs = (
            [r for r in self.results[1:] if r["success"]]
            if len(self.results) > 1
            else []
        )
        cached_times = [r["time"] for r in cached_runs] if cached_runs else []

        # Retry analysis
        runs_with_retries = [r for r in self.results if r["retries_detected"]]
        runs_with_cache = [r for r in self.results if r["used_cache"]]

        # Time to failure (for failed runs)
        failed_times = [r["time"] for r in failed] if failed else []

        stats = {
            "total_runs": len(self.results),
            "successful_runs": len(successful),
            "failed_runs": len(failed),
            "success_rate": (
                len(successful) / len(self.results) * 100 if self.results else 0
            ),
            # Timing stats (all successful runs)
            "timing": {
                "average": mean(times) if times else 0,
                "median": median(times) if times else 0,
                "min": min(times) if times else 0,
                "max": max(times) if times else 0,
                "stdev": stdev(times) if len(times) > 1 else 0,
                "p95": (
                    sorted(times)[int(len(times) * 0.95)]
                    if len(times) >= 20
                    else (max(times) if times else 0)
                ),
                "p99": (
                    sorted(times)[int(len(times) * 0.99)]
                    if len(times) >= 20
                    else (max(times) if times else 0)
                ),
            },
            # First run vs cached runs
            "first_run": {
                "time": first_run["time"] if first_run else 0,
                "success": first_run["success"] if first_run else False,
                "used_cache": first_run["used_cache"] if first_run else False,
            },
            "cached_runs": {
                "count": len(cached_runs),
                "average_time": mean(cached_times) if cached_times else 0,
                "median_time": median(cached_times) if cached_times else 0,
                "min_time": min(cached_times) if cached_times else 0,
                "max_time": max(cached_times) if cached_times else 0,
            },
            # Retry analysis
            "retries": {
                "runs_with_retries": len(runs_with_retries),
                "retry_rate": (
                    len(runs_with_retries) / len(self.results) * 100
                    if self.results
                    else 0
                ),
                "retry_details": [
                    {"run": r["run"], "details": r["retry_details"], "time": r["time"]}
                    for r in runs_with_retries
                ],
            },
            # Cache usage
            "cache_usage": {
                "runs_with_cache": len(runs_with_cache),
                "cache_hit_rate": (
                    len(runs_with_cache) / len(self.results) * 100
                    if self.results
                    else 0
                ),
            },
            # Failure analysis
            "failures": {
                "count": len(failed),
                "average_time_to_failure": mean(failed_times) if failed_times else 0,
                "details": [
                    {"run": r["run"], "time": r["time"], "error": r["error"]}
                    for r in failed
                ],
            },
            # Overall test duration
            "test_duration_seconds": (
                self.end_time - self.start_time
                if self.start_time and self.end_time
                else 0
            ),
        }

        return stats

    def generate_report(self, stats: dict[str, Any]):
        """Generate human-readable report"""
        report_lines = []

        report_lines.append("=" * 80)
        report_lines.append("FareCraft Performance Test - Final Report")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Test metadata
        report_lines.append("TEST CONFIGURATION")
        report_lines.append("-" * 80)
        report_lines.append(f"Docker Image: {self.docker_image}")
        report_lines.append(f"Total Runs: {stats['total_runs']}")
        report_lines.append(
            f"Test Duration: {stats['test_duration_seconds']:.1f}s ({stats['test_duration_seconds']/60:.1f} minutes)"
        )
        report_lines.append(
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        report_lines.append("")

        # Success rate
        report_lines.append("SUCCESS RATE")
        report_lines.append("-" * 80)
        report_lines.append(
            f"Successful: {stats['successful_runs']}/{stats['total_runs']} ({stats['success_rate']:.1f}%)"
        )
        report_lines.append(
            f"Failed: {stats['failed_runs']}/{stats['total_runs']} ({100-stats['success_rate']:.1f}%)"
        )
        report_lines.append("")

        # Performance metrics
        report_lines.append("PERFORMANCE METRICS (Successful Runs Only)")
        report_lines.append("-" * 80)
        report_lines.append(f"Average Time: {stats['timing']['average']:.2f}s")
        report_lines.append(f"Median Time: {stats['timing']['median']:.2f}s")
        report_lines.append(f"Min Time: {stats['timing']['min']:.2f}s")
        report_lines.append(f"Max Time: {stats['timing']['max']:.2f}s")
        report_lines.append(f"Std Deviation: {stats['timing']['stdev']:.2f}s")
        report_lines.append(f"95th Percentile: {stats['timing']['p95']:.2f}s")
        report_lines.append(f"99th Percentile: {stats['timing']['p99']:.2f}s")
        report_lines.append("")

        # First run vs cached
        report_lines.append("CACHE PERFORMANCE")
        report_lines.append("-" * 80)
        report_lines.append("First Run (Cookie Generation):")
        report_lines.append(f"  • Time: {stats['first_run']['time']:.2f}s")
        report_lines.append(
            f"  • Success: {'✅' if stats['first_run']['success'] else '❌'}"
        )
        report_lines.append(
            f"  • Used Cache: {'Yes' if stats['first_run']['used_cache'] else 'No'}"
        )
        report_lines.append("")
        report_lines.append(f"Cached Runs (Runs 2-{stats['total_runs']}):")
        report_lines.append(f"  • Count: {stats['cached_runs']['count']}")
        report_lines.append(
            f"  • Average Time: {stats['cached_runs']['average_time']:.2f}s"
        )
        report_lines.append(
            f"  • Median Time: {stats['cached_runs']['median_time']:.2f}s"
        )
        report_lines.append(f"  • Min Time: {stats['cached_runs']['min_time']:.2f}s")
        report_lines.append(f"  • Max Time: {stats['cached_runs']['max_time']:.2f}s")
        report_lines.append("")
        report_lines.append(
            f"Cache Hit Rate: {stats['cache_usage']['cache_hit_rate']:.1f}% ({stats['cache_usage']['runs_with_cache']}/{stats['total_runs']})"
        )
        report_lines.append("")

        # Reliability
        report_lines.append("RELIABILITY ANALYSIS")
        report_lines.append("-" * 80)
        report_lines.append(
            f"Runs with Retries: {stats['retries']['runs_with_retries']}/{stats['total_runs']} ({stats['retries']['retry_rate']:.1f}%)"
        )

        if stats["retries"]["retry_details"]:
            report_lines.append("\nRetry Details:")
            for detail in stats["retries"]["retry_details"]:
                report_lines.append(
                    f"  • Run #{detail['run']}: {', '.join(detail['details'])} (took {detail['time']:.2f}s)"
                )
        else:
            report_lines.append(
                "  ✅ No retries needed - all runs succeeded on first attempt!"
            )

        report_lines.append("")

        # Failure analysis
        if stats["failures"]["count"] > 0:
            report_lines.append("FAILURE ANALYSIS")
            report_lines.append("-" * 80)
            report_lines.append(f"Total Failures: {stats['failures']['count']}")
            report_lines.append(
                f"Average Time to Failure: {stats['failures']['average_time_to_failure']:.2f}s"
            )
            report_lines.append("\nFailure Details:")
            for fail in stats["failures"]["details"]:
                report_lines.append(
                    f"  • Run #{fail['run']}: {fail['error']} (failed at {fail['time']:.2f}s)"
                )
            report_lines.append("")

        # Conclusion
        report_lines.append("CONCLUSION")
        report_lines.append("-" * 80)
        if stats["success_rate"] >= 95 and stats["timing"]["median"] < 6.0:
            report_lines.append("✅ EXCELLENT - High reliability and fast performance")
        elif stats["success_rate"] >= 90:
            report_lines.append("✅ GOOD - Reliable performance")
        elif stats["success_rate"] >= 80:
            report_lines.append("⚠️  ACCEPTABLE - Meets minimum reliability threshold")
        else:
            report_lines.append(
                "❌ NEEDS IMPROVEMENT - Reliability below acceptable threshold"
            )

        report_lines.append("")
        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def generate_graphs(self, stats: dict[str, Any]):
        """Generate comprehensive performance visualization"""
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️  Skipping graph generation (matplotlib not installed)")
            return

        print("\n📊 Generating performance graphs...")

        # Create figure with subplots
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # Color scheme
        color_success = "#2ecc71"  # Green
        color_retry = "#f39c12"  # Orange
        color_failure = "#e74c3c"  # Red
        color_first_run = "#3498db"  # Blue

        # Extract data
        run_numbers = [r["run"] for r in self.results]
        times = [r["time"] for r in self.results]
        # successes = [r["success"] for r in self.results]
        # retries = [r["retries_detected"] for r in self.results]

        # Colors for each run
        colors = []
        for i, r in enumerate(self.results):
            if i == 0:
                colors.append(color_first_run)  # First run (special)
            elif not r["success"]:
                colors.append(color_failure)
            elif r["retries_detected"]:
                colors.append(color_retry)
            else:
                colors.append(color_success)

        # 1. Main Timeline Plot (spans 2 columns)
        ax1 = fig.add_subplot(gs[0:2, :2])
        bars = ax1.bar(
            run_numbers,
            times,
            color=colors,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        # Add median line
        if stats["timing"]["median"] > 0:
            ax1.axhline(
                y=stats["timing"]["median"],
                color="blue",
                linestyle="-",
                linewidth=1.5,
                label=f'Median ({stats["timing"]["median"]:.2f}s)',
                alpha=0.7,
            )

        ax1.set_xlabel("Run Number", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Time (seconds)", fontsize=12, fontweight="bold")
        ax1.set_title(
            "FareCraft Performance: 50 Consecutive Runs\n(Cold Start → Cached)",
            fontsize=14,
            fontweight="bold",
            pad=20,
        )
        ax1.grid(axis="y", alpha=0.3, linestyle="--")
        ax1.set_xlim(0, len(run_numbers) + 1)

        # Custom legend
        legend_elements = [
            mpatches.Patch(color=color_first_run, label="Run #1 (Cold Start)"),
            mpatches.Patch(color=color_success, label="Success (Cached)"),
            mpatches.Patch(color=color_retry, label="Success with Retries"),
            mpatches.Patch(color=color_failure, label="Failure"),
        ]
        ax1.legend(handles=legend_elements, loc="upper right", fontsize=10)

        # 2. Distribution Histogram (top right)
        ax2 = fig.add_subplot(gs[0, 2])

        # Separate first run from cached runs
        cached_times = [r["time"] for r in self.results[1:] if r["success"]]

        if cached_times:
            ax2.hist(
                cached_times, bins=15, color=color_success, alpha=0.7, edgecolor="black"
            )
            ax2.axvline(
                stats["timing"]["median"],
                color="red",
                linestyle="--",
                linewidth=2,
                label=f'Median: {stats["timing"]["median"]:.2f}s',
            )

        ax2.set_xlabel("Time (seconds)", fontsize=10)
        ax2.set_ylabel("Frequency", fontsize=10)
        ax2.set_title(
            "Cached Runs Distribution\n(Excludes Run #1)",
            fontsize=11,
            fontweight="bold",
        )
        ax2.legend(fontsize=8)
        ax2.grid(axis="y", alpha=0.3)

        # 3. Success Rate Pie Chart (middle right)
        ax3 = fig.add_subplot(gs[1, 2])

        success_count = stats["successful_runs"]
        failure_count = stats["failed_runs"]

        sizes = [success_count, failure_count] if failure_count > 0 else [success_count]
        labels = (
            [f"Success\n{success_count}/50", f"Failed\n{failure_count}/50"]
            if failure_count > 0
            else [f"Success\n{success_count}/50"]
        )
        colors_pie = (
            [color_success, color_failure] if failure_count > 0 else [color_success]
        )

        _ = ax3.pie(
            sizes,
            labels=labels,
            colors=colors_pie,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 10, "fontweight": "bold"},
        )
        ax3.set_title("Success Rate", fontsize=11, fontweight="bold")

        # 4. Key Metrics Box (bottom row, left)
        ax4 = fig.add_subplot(gs[2, 0])
        ax4.axis("off")

        metrics_text = f"""
        KEY PERFORMANCE METRICS

        Overall Average:      {stats['timing']['average']:.2f}s
        Median (Typical):     {stats['timing']['median']:.2f}s
        Min Time:             {stats['timing']['min']:.2f}s
        Max Time:             {stats['timing']['max']:.2f}s
        Std Deviation:        {stats['timing']['stdev']:.2f}s

        95th Percentile:      {stats['timing']['p95']:.2f}s
        99th Percentile:      {stats['timing']['p99']:.2f}s

        First Run (Cold):     {stats['first_run']['time']:.2f}s
        Cached Avg:           {stats['cached_runs']['average_time']:.2f}s
        """

        ax4.text(
            0.1,
            0.5,
            metrics_text,
            fontsize=10,
            family="monospace",
            verticalalignment="center",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )

        # 5. Reliability Summary (bottom row, middle)
        ax5 = fig.add_subplot(gs[2, 1])
        ax5.axis("off")

        summary_text = f"""
        RELIABILITY SUMMARY

        Success Rate:         {stats['success_rate']:.1f}%
        Total Runs:           {stats['total_runs']}
        Successful:           {stats['successful_runs']}
        Failed:               {stats['failed_runs']}

        Retry Rate:           {stats['retries']['retry_rate']:.1f}%
        Runs with Retries:    {stats['retries']['runs_with_retries']}

        Cache Hit Rate:       {stats['cache_usage']['cache_hit_rate']:.1f}%

        Test Duration:        {stats['test_duration_seconds']/60:.1f} minutes

        Status: {'✅ EXCELLENT' if stats['success_rate'] >= 95 else '✅ GOOD' if stats['success_rate'] >= 90 else '⚠️ ACCEPTABLE'}
        """

        ax5.text(
            0.1,
            0.5,
            summary_text,
            fontsize=10,
            family="monospace",
            verticalalignment="center",
            bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.3),
        )

        # 6. Cache Performance (bottom row, right)
        ax6 = fig.add_subplot(gs[2, 2])

        categories = ["First Run\n(Cold Start)", "Cached Runs\n(Avg)"]
        values = [stats["first_run"]["time"], stats["cached_runs"]["average_time"]]
        bar_colors = [color_first_run, color_success]

        bars = ax6.bar(
            categories, values, color=bar_colors, alpha=0.7, edgecolor="black"
        )
        ax6.set_ylabel("Time (seconds)", fontsize=10)
        ax6.set_title("Cache Performance Impact", fontsize=11, fontweight="bold")
        ax6.grid(axis="y", alpha=0.3)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax6.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.2f}s",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # Overall title
        fig.suptitle(
            "FareCraft 50-Run Benchmark Results", fontsize=18, fontweight="bold", y=0.98
        )

        # Save figure
        plt.savefig("test_performance_graph.png", dpi=300, bbox_inches="tight")
        print("✅ Performance graph saved to: test_performance_graph.png")
        plt.close()

    def save_results(self, stats: dict[str, Any]):
        """Save results to JSON and text report"""
        # Save detailed JSON
        output = {
            "metadata": {
                "test_name": "FareCraft 50-Run Performance Test",
                "docker_image": self.docker_image,
                "total_runs": self.num_runs,
                "timestamp": datetime.now().isoformat(),
                "test_duration_seconds": stats["test_duration_seconds"],
            },
            "statistics": stats,
            "raw_results": self.results,
        }

        with open("test_results.json", "w") as f:
            json.dump(output, f, indent=2)

        print("\n✅ Detailed results saved to: test_results.json")

        # Save human-readable report
        report = self.generate_report(stats)
        with open("test_report.txt", "w") as f:
            f.write(report)

        print("✅ Human-readable report saved to: test_report.txt")

        # Generate performance graphs
        self.generate_graphs(stats)

        # Print report to console
        print("\n" + report)

    def run(self):
        """Main test execution"""
        self.setup()
        self.run_all_tests()
        stats = self.calculate_statistics()
        self.save_results(stats)

        # Return exit code based on results
        if stats["success_rate"] >= 90:
            return 0
        else:
            return 1


def main():
    """Entry point"""
    runner = TestRunner(num_runs=50)
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
