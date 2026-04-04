# Phase 2 Modules - Quick Reference

## Module Overview

### 1. Circuit Breaker (`circuit_breaker.py`)
**Purpose:** Prevent cascading failures when external APIs are down

**Key Exports:**
```python
from circuit_breaker import (
    CircuitState,          # Enum: CLOSED, OPEN, HALF_OPEN
    CircuitBreaker,        # Main class
    CircuitBreakerRegistry,# Global registry for all breakers
    with_circuit_breaker,  # @decorator for async functions
)

# Pre-configured breakers:
from circuit_breaker import (
    BREAKER_COINCAP,
    BREAKER_COINMARKETCAP,
    BREAKER_FIREBASE,
    BREAKER_EMAIL,
    BREAKER_TELEGRAM,
    BREAKER_NOWPAYMENTS,
)
```

**Configuration:**
```python
CircuitBreaker(
    name="my-api",
    failure_threshold=5,        # Fail after 5 consecutive errors
    timeout_seconds=60,         # Wait 60s before trying HALF_OPEN
    success_threshold=2,        # Need 2 successes to go to CLOSED
    expected_exception=Exception # What to catch
)
```

**Usage:**
```python
# As decorator (automatic)
@with_circuit_breaker(BREAKER_COINCAP, fallback=fallback_handler)
async def fetch_prices():
    pass

# Manual control
if BREAKER_COINCAP.can_attempt_request():
    try:
        result = await api.call()
        BREAKER_COINCAP.record_success()
    except Exception as e:
        BREAKER_COINCAP.record_failure()
        
# Check status
if BREAKER_COINCAP.is_open():
    return fallback_data()
```

---

### 2. Request Retry (`request_retry.py`)
**Purpose:** Handle transient failures with exponential backoff + jitter

**Key Exports:**
```python
from request_retry import (
    RetryConfig,           # Configuration class
    RetryableException,    # Exception type to retry on
    with_retry,            # @decorator for functions
    retry_with_backoff,    # Function for manual retry
    RetryStats,            # Track retry statistics
)

# Pre-configured policies:
from request_retry import (
    RETRY_DEFAULT,         # 3 attempts, 100ms initial
    RETRY_AGGRESSIVE,      # 5 attempts, 50ms initial
    RETRY_CONSERVATIVE,    # 2 attempts, 200ms initial
    RETRY_API,            # 4 attempts, optimized for HTTP
)
```

**Configuration:**
```python
RetryConfig(
    max_attempts=4,
    initial_delay_ms=100,
    exponential_base=2.0,   # 100ms → 200ms → 400ms → 800ms
    max_delay_ms=10000,     # Cap at 10 seconds
    jitter=0.1,             # ±10% random jitter
    retryable_exceptions=(ConnectionError, TimeoutError)
)
```

**Usage:**
```python
# As decorator
@with_retry(RETRY_API)
async def fetch_data():
    return await external_api.get()

# Manual retry
result = await retry_with_backoff(
    fetch_data,
    config=RETRY_API,
    name="fetch-data"
)

# Get statistics
stats = RetryStats.get_stats()  # Shows retry effectiveness
```

---

### 3. Cache Decorator (`cache_decorator.py`)
**Purpose:** Intelligent response caching with Redis integration

**Key Exports:**
```python
from cache_decorator import (
    CacheConfig,           # Configuration class
    cached_endpoint,       # @decorator for routes
    CacheStats,            # Track hit/miss rates
    get_cache_headers,     # Generate Cache-Control headers
    cache_warmer,          # Pre-populate cache
)

# Pre-configured policies:
from cache_decorator import (
    CACHE_SHORT,           # 60 seconds
    CACHE_MEDIUM,          # 300 seconds (5 min)
    CACHE_LONG,            # 3600 seconds (1 hour)
    CACHE_PRICES,          # 60 sec, varies by symbol
    CACHE_PORTFOLIO,       # 120 sec, varies by user
    CACHE_TRADING,         # 30 sec, varies by pair
    CACHE_ASSETS,          # 3600 sec, varies by type
)
```

**Configuration:**
```python
CacheConfig(
    ttl_seconds=300,
    cache_key_prefix="myapp:",
    vary_by=["user_id", "symbol"],  # Create separate cache keys
    enable_etag=True,               # Generate ETags
    enable_compression=True,         # Gzip cached values
)
```

**Usage:**
```python
# As decorator with config
@router.get("/prices/{symbol}")
@cached_endpoint(config=CACHE_PRICES)
async def get_price(symbol: str):
    return await fetch_price(symbol)

# Override headers
from fastapi import Response
response.headers.update(get_cache_headers(ttl_seconds=3600))

# Manual cache warming
await cache_warmer("key", value, ttl_seconds=3600)

# Cache statistics
stats = CacheStats.get_stats()  # Hit rate, miss rate, etc
```

---

### 4. Database Optimization (`db_optimization.py`)
**Purpose:** Pre-defined MongoDB indexes and query optimization

**Key Exports:**
```python
from db_optimization import (
    QueryOptimization,     # Main class with indexes
    create_all_recommended_indexes,  # Async function
    IndexStatistics,       # Track index usage
    analyze_collection_stats,  # Get collection metrics
)
```

**Pre-configured Indexes:**
```python
QueryOptimization.RECOMMENDED_INDEXES = {
    "users": [
        {"keys": [("email", 1)], "unique": True},
        {"keys": [("created_at", -1)]},
        {"keys": [("verified", 1), ("created_at", -1)]},
        {"keys": [("kyc_status", 1), ("created_at", -1)]},
    ],
    "portfolio": [
        {"keys": [("user_id", 1)], "unique": True},
        {"keys": [("user_id", 1), ("updated_at", -1)]},
    ],
    # ... 6 more collections
}
```

**Usage:**
```python
# Create all indexes at startup
@app.on_event("startup")
async def startup():
    await create_all_recommended_indexes(db)

# Analyze collection
stats = await analyze_collection_stats(db)
print(stats["users"]["index_count"])  # How many indexes

# Get optimization tips
tips = QueryOptimization.get_query_optimization_tips()
```

**Collections Optimized:**
- users (unique keys, timestamps, KYC status)
- portfolio (user association, update tracking)
- transactions (user+date compound, type filtering, hash lookup)
- orders (user+date, status filtering, trading pair)
- alerts (user+active, symbol+active)
- stakes (user+status, date tracking)
- referrals (user tracking, status)
- kyc_documents (user+timestamp, pending documents)

---

### 5. Performance Monitoring (`performance_monitoring.py`)
**Purpose:** Track Web Vitals, API metrics, and integrate with Sentry

**Key Exports:**
```python
from performance_monitoring import (
    CoreWebVital,          # Dataclass for vital
    PerformanceMetrics,    # Main metrics tracker
    RequestTimer,          # Context manager for timing
    send_metrics_to_sentry,  # Send to Sentry
    performance_metrics,   # Global singleton instance
)
```

**Core Web Vitals Tracked:**
```python
# Values and thresholds:
LCP (Largest Contentful Paint)
  - Good: < 2.5s
  - Poor: >= 4.0s

FID (First Input Delay)
  - Good: < 100ms
  - Poor: >= 300ms

CLS (Cumulative Layout Shift)
  - Good: < 0.1
  - Poor: >= 0.25

TTFB (Time to First Byte)
  - Good: < 600ms
  - Poor: >= 1800ms

FCP (First Contentful Paint)
  - Good: < 1.8s
  - Poor: >= 3.0s
```

**Usage:**
```python
# Record vital from frontend
@router.post("/api/metrics/vitals")
async def record_vital(name: str, value: float):
    vital = performance_metrics.record_vital(name, value)
    return {"status": vital.status}

# Time API requests
async with RequestTimer("fetch-prices"):
    result = await get_prices()

# Record API timing manually
performance_metrics.record_api_timing(
    endpoint="/prices",
    method="GET",
    response_time_ms=45.2,
    status_code=200,
)

# Get summary (all metrics)
summary = performance_metrics.get_summary()

# Send to Sentry
await send_metrics_to_sentry(summary)
```

---

## Dependency Graph

```
┌─────────────────────────────────┐
│   backend/server.py             │
│   (main FastAPI app)            │
└────────┬────────────────────────┘
         │
         ├──→ circuit_breaker.py (no dependencies)
         │
         ├──→ request_retry.py (no dependencies)
         │
         ├──→ cache_decorator.py
         │    └──→ redis_cache.py (existing)
         │
         ├──→ db_optimization.py
         │    └──→ Motor (MongoDB driver)
         │
         └──→ performance_monitoring.py
              └──→ Sentry SDK (existing)

Routes apply decorators:
├── GET /prices → @cached_endpoint + @with_retry
├── GET /portfolio/{user_id} → @cached_endpoint
├── GET /markets → @cached_endpoint + @with_retry
└── POST /send-email → @with_retry
```

---

## Decorator Application Order (Important!)

**Correct order (cache → retry → circuit-breaker):**
```python
@cached_endpoint(CACHE_PRICES)      # 1. Cache OUTER (check cache first)
@with_retry(RETRY_API)               # 2. Retry MIDDLE (if cache miss, retry)
@with_circuit_breaker(BREAKER_API, fallback=fallback)  # 3. Breaker INNER (if retries fail)
async def fetch_prices():
    pass
```

**Why this order matters:**
1. Cache hit bypasses everything (fastest)
2. Cache miss triggers retries (resilient)
3. All retries fail triggers circuit breaker (graceful degradation)

---

## Configuration Recommendations

**For production:**
```python
# Circuit breakers - Fast fail
CircuitBreaker(
    failure_threshold=5,      # 5 errors = open
    timeout_seconds=60,       # Try recovery after 60s
    success_threshold=2,      # 2 successes = close
)

# Retries - Exponential backoff
RetryConfig(
    max_attempts=4,
    initial_delay_ms=100,
    max_delay_ms=10000,
    jitter=0.1,
)

# Cache - Vary by user/query
CacheConfig(
    vary_by=["user_id", "symbol"],
    enable_compression=True,
)

# Database - All recommended indexes
await create_all_recommended_indexes(db)
```

**For development:**
```python
# Circuit breakers - More lenient
CircuitBreaker(
    failure_threshold=10,
    timeout_seconds=10,
)

# Retries - Single attempt (faster testing)
RetryConfig(
    max_attempts=1,
)

# Cache - Short TTL
CacheConfig(ttl_seconds=60)
```

---

## Monitoring Endpoints Added
```
GET  /health                    → Circuit breaker status + performance
GET  /api/monitor/performance   → All performance metrics
GET  /api/monitor/circuit-breakers → Breaker states
POST /api/metrics/vitals        → Record Core Web Vitals
```

---

## Performance Impact Estimation

| Feature | Before | After | Improvement |
|---------|--------|-------|-------------|
| Cached endpoint latency | 200-500ms | 5-10ms | 95% ↓ |
| API call failures | 15% | 2% | 87% ↓ |
| DB query time | 100-500ms | 20-100ms | 60-80% ↓ |
| Network bandwidth | 100% | 50-60% | 40-50% ↓ |
| External API calls | 100% | 60-80% | 20-40% ↓ |

---

## Next Steps

1. **Review** the specific module you want to integrate first
2. **Apply decorators** to routes/functions as shown in checklist
3. **Test locally**: `pytest tests/ -v`
4. **Run Codacy**: Verify no new issues introduced
5. **Deploy** to Render
6. **Monitor** using new monitoring endpoints

All 5 modules are ready to import and use! 🚀
