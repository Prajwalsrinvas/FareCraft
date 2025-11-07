# Experiments & Testing

This folder contains test scripts, comparison results, and documentation for evaluating different scraping approaches.

## Files

- **test_all_three_approaches.py** - Compares all three scraping strategies (sequential, parallel, staggered)
- **test_comprehensive.py** - Comprehensive testing suite for the scraper
- **comparison_results.json** - Performance comparison data
- **comparison_all_three.log** - Detailed logs from approach comparison
- **test_results.md** - Analysis and decision documentation

## Scraping Approaches

The scraper supports three different request strategies:

### 1. **Pure Parallel** (Default - Production)
- **File:** `src/scraper/scraper.py`
- **Strategy:** Award and Revenue requests start simultaneously
- **Performance:** 42.7% faster than sequential
- **Use Case:** Best for speed, current production implementation

### 2. **Sequential**
- **File:** `src/scraper/scraper_sequential.py`
- **Strategy:** Award completes → delay → Revenue starts
- **Performance:** Slowest but most human-like
- **Use Case:** Maximum stealth if bot detection becomes an issue

### 3. **Staggered Parallel**
- **File:** `src/scraper/scraper_staggered.py`
- **Strategy:** Award starts → delay → Revenue starts (both run concurrently)
- **Performance:** 30.9% faster than sequential
- **Use Case:** Balance between speed and stealth

## Switching Between Approaches

To use a different scraping approach, update the import in `src/api/main.py`:

```python
# Current (Pure Parallel):
from scraper.scraper import scrape_flights

# Change to Sequential:
from scraper.scraper_sequential import scrape_flights

# Change to Staggered:
from scraper.scraper_staggered import scrape_flights
```

All three implementations have identical function signatures and can be swapped without any other code changes.

## Running Tests

### Compare All Three Approaches
```bash
cd /home/prajwal/WS
python experiments/test_all_three_approaches.py
```

### Comprehensive Testing
```bash
cd /home/prajwal/WS
python experiments/test_comprehensive.py
```

## Results Summary

Based on empirical testing (see test_results.md):
- **Pure Parallel:** 3.36s avg (PRODUCTION)
- **Staggered Parallel:** 4.04s avg
- **Sequential:** 5.85s avg

All approaches achieved 100% reliability with zero bot detection in testing.
