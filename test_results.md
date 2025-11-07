# Request Strategy Comparison: Sequential vs Parallel

**Date:** November 7, 2025
**Test Duration:** 1.9 minutes
**Total API Requests:** 24 (100% success rate)

## Executive Summary

Tested 3 different approaches for making Award and Revenue API requests to determine optimal balance between **speed** and **bot detection risk**. All approaches achieved 100% reliability with zero errors.

**Final Decision:** ✅ **Pure Parallel** - 42.7% faster with no bot detection observed.

---

## Approaches Tested

### 1. Sequential (`scraper_sequential.py`)
- Award request completes → random delay (0.2-1.0s) → Revenue request starts
- **Pros:** Most human-like, lowest bot detection risk
- **Cons:** Slowest due to no parallelism

### 2. Pure Parallel (`scraper.py.py`) ⭐ **PRODUCTION**
- Award and Revenue requests start at exact same millisecond via ThreadPoolExecutor
- **Pros:** Fastest execution, both requests run concurrently
- **Cons:** Simultaneous identical requests could theoretically trigger bot detection

### 3. Staggered Parallel (`scraper_staggered.py`)
- Award starts → random delay (0.2-1.0s) → Revenue starts (both run concurrently)
- **Pros:** Speed/safety middle ground
- **Cons:** More complex than pure approaches

---

## Test Methodology

**Test Structure:**
- Each approach: 1 fresh scrape (with cookie generation) + 3 cached scrapes
- 10-second cooldown between approach tests
- Database cleared between approaches for fair comparison
- Performance measured on cached runs only (excludes 6s cookie overhead)

**Fairness Controls:**
- ✅ Fresh cookies for each approach
- ✅ Same route (LAX → JFK)
- ✅ Same date (2025-12-15)
- ✅ 10s waits to prevent rate limit bleed-over

---

## Results

| Approach | Avg Time | Min | Max | Speed vs Sequential | Errors |
|----------|----------|-----|-----|---------------------|--------|
| **Sequential** | 5.85s | 5.67s | 6.11s | baseline | 0 |
| **Pure Parallel** ⭐ | **3.36s** | 2.99s | 3.60s | **42.7% faster** | 0 |
| **Staggered** | 4.04s | 3.87s | 4.15s | 30.9% faster | 0 |

**Bot Detection:** ✅ Zero 403/429 errors across all 24 requests
**Reliability:** 100% success rate for all approaches
**Winner:** Pure Parallel - 2.5 seconds faster than Sequential

---

## Decision Rationale

**Why Pure Parallel:**
1. **Performance:** 42.7% faster = significant competitive advantage
2. **Empirical Evidence:** Zero bot detection in testing (24 requests)
3. **Contest Context:** Speed matters when "multiple scrapers successfully complete"
4. **Technical Reality:** curl_cffi sessions are NOT thread-safe (proven via testing), so separate sessions required anyway
5. **Risk Mitigation:** Retry logic with exponential backoff handles rate limits

**Why NOT Sequential:**
- Only 2.5s difference, but in competition context, speed wins tie-breakers
- If bot detection occurs, retry mechanism will regenerate cookies

**Why NOT Staggered:**
- Middle ground offers no compelling advantage
- Added complexity without clear benefit over pure parallel

---

## Implementation

**Production File:** `src/scraper/scraper.py`
**Backup Files:** All 3 versions retained for documentation
**Key Changes:**
- ThreadPoolExecutor with max_workers=2
- Separate curl_cffi sessions per thread (required for thread safety)
- Both requests use identical cookies from single Camoufox session

---

## Logs & Data

**Full Test Output:** [comparison_all_three.log](comparison_all_three.log)
**Structured Data:** [comparison_results.json](comparison_results.json)

---

**Conclusion:** Pure parallel approach provides best performance with no observed downside. If bot detection emerges in production, can fallback to sequential with single line change.
