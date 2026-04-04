# Circuit Breaker Pattern - Phase 3 Implementation Guide

## Overview

The CryptoVault backend implements the **Circuit Breaker Pattern** to provide enterprise-grade fault tolerance for external service dependencies. This prevents cascading failures and enables graceful degradation when external APIs become unavailable.

## Why Circuit Breaker Pattern?

External API calls are inherently unreliable due to network latency, rate limiting, service outages, and timeouts. Without circuit breakers:

- **Cascading Failures**: One failing API can cause the entire application to fail
- **Resource Waste**: Wasted resources retrying unavailable services
- **Slow Failure**: Requests timeout waiting for unreachable services
- **No Self-Healing**: System remains broken until manually restarted

With circuit breakers:

- **Fast Failure**: Requests fail immediately when service is down
- **Graceful Degradation**: System remains partially operational
- **Self-Healing**: Automatic recovery when service returns
- **Resource Conservation**: No wasted retries or timeouts

## Architecture

### Three-State Machine

```
┌─────────────┐
│   CLOSED    │ <- Normal operation, all requests go through
└──────┬──────┘
       │ (failure_threshold exceeded)
       ↓
┌─────────────┐
│    OPEN     │ <- Service failing, requests rejected immediately
└──────┬──────┘
       │ (timeout_seconds elapsed)
       ↓
┌─────────────┐
│ HALF_OPEN   │ <- Testing if service recovered
└──────┬──────┘
       │
       ├─ success → CLOSED (recovery confirmed)
       └─ failure → OPEN  (still broken)
```

### Five Protected Services

| Service | Breaker Name | Purpose | Fallback Behavior |
|---------|--------------|---------|-------------------|
| **CoinCap** | `BREAKER_COINCAP` | Price data | Return empty list `[]` |
| **Telegram** | `BREAKER_TELEGRAM` | Admin notifications | Return `False` (silent fail) |
| **NowPayments** | `BREAKER_NOWPAYMENTS` | Payment processing | Return error dict |
| **Firebase** | `BREAKER_FIREBASE` | Push notifications | Mock mode fallback |
| **Email** | `BREAKER_EMAIL` | User emails | Mock/fallback provider |

## Implementation Details

### Core Components

#### 1. CircuitBreaker Class

Individual breaker managing a single external service:

```python
from circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    name="coincap",
    failure_threshold=5,        # Open after 5 failures
    timeout_seconds=300,        # Recovery attempt every 5 minutes
    initial_backoff_seconds=1,  # Start with 1s backoff
    max_backoff_seconds=300     # Cap at 5 minutes
)

# Check if available
if breaker.is_available():
    result = await call_coincap_api()
    breaker.record_success(response_time_ms)
else:
    result = fallback_value
    # Optionally attempt HALF_OPEN recovery
```

#### 2. CircuitBreakerRegistry (Singleton)

Manages all 5 circuit breakers:

```python
from circuit_breaker import CircuitBreakerRegistry, BREAKER_COINCAP, BREAKER_TELEGRAM

registry = CircuitBreakerRegistry.get_instance()

# All breakers are pre-configured:
coincap_breaker = registry.get("coincap")
telegram_breaker = registry.get("telegram")

# Or use direct imports:
if BREAKER_COINCAP.is_available():
    prices = await fetch_prices()
```

#### 3. @with_circuit_breaker Decorator

Automatically applies circuit breaker to async functions:

```python
from circuit_breaker import with_circuit_breaker, BREAKER_COINCAP

@with_circuit_breaker(breaker=BREAKER_COINCAP, fallback_func=lambda *args, **kwargs: [])
async def fetch_crypto_prices(coin_ids):
    """Automatically protected: returns [] if breaker is OPEN"""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.coingecko.com/...")
        return response.json()

# When circuit is OPEN, returns [] immediately (no timeout)
prices = await fetch_crypto_prices(["bitcoin", "ethereum"])
```

### Exponential Backoff Strategy

When a service fails, the circuit breaker uses exponential backoff to prevent overwhelming the failing service:

```
Failure 1: Reject immediately
Failure 2: Next recovery attempt in 1 second
Failure 3: Next recovery attempt in 2 seconds
Failure 4: Next recovery attempt in 4 seconds
Failure 5: Next recovery attempt in 8 seconds
...
Max:     Recovery attempt every 5 minutes
```

## Configuration

### Default Configuration

```python
BREAKER_COINCAP = CircuitBreaker(
    name="coincap",
    failure_threshold=5,         # Open after 5 consecutive failures
    timeout_seconds=60,          # Attempt recovery after 60 seconds
    initial_backoff_seconds=1,
    max_backoff_seconds=300
)

BREAKER_TELEGRAM = CircuitBreaker(
    name="telegram",
    failure_threshold=3,         # Lower threshold for notifications (less critical)
    timeout_seconds=30,
    initial_backoff_seconds=1,
    max_backoff_seconds=300
)

# Similar configurations for BREAKER_NOWPAYMENTS, BREAKER_FIREBASE, BREAKER_EMAIL
```

### Custom Configuration

To modify circuit breaker settings:

```python
from circuit_breaker import CircuitBreakerRegistry

registry = CircuitBreakerRegistry.get_instance()
coincap = registry.get("coincap")

# Adjust thresholds
coincap.failure_threshold = 10
coincap.timeout_seconds = 120
```

## Monitoring & Observability

### Monitoring Dashboard

Monitor all circuit breakers in real-time:

```bash
# Get all breaker states
GET /api/admin/circuit-breakers

# Get specific breaker
GET /api/admin/circuit-breakers/{breaker_name}

# Get state change history
GET /api/admin/circuit-breakers/{breaker_name}/history?limit=100

# Get system health
GET /api/admin/health/circuit-breakers

# Prometheus metrics
GET /api/admin/metrics
```

### Example Dashboard Response

```json
{
  "timestamp": "2026-04-04T12:00:00Z",
  "system_uptime_percentage": 99.8,
  "breaker_states": {
    "closed": 4,
    "open": 1,
    "half_open": 0,
    "total": 5
  },
  "total_requests": 50000,
  "total_successful_requests": 49900,
  "total_failed_requests": 100,
  "failing_services": ["coincap"],
  "recovering_services": [],
  "system_status": "DEGRADED"
}
```

### Prometheus Metrics

All metrics are exported in Prometheus format for collection by monitoring systems:

```
# Circuit breaker states (1=CLOSED, 2=OPEN, 3=HALF_OPEN)
cryptovault_circuit_breaker_state{breaker="coincap"} 2
cryptovault_circuit_breaker_state{breaker="telegram"} 1
...

# Request counts
cryptovault_circuit_breaker_requests_total{breaker="coincap"} 1000
cryptovault_circuit_breaker_failures_total{breaker="coincap"} 50

# Uptime percentages
cryptovault_circuit_breaker_uptime_percentage{breaker="coincap"} 95.0

# Response times
cryptovault_circuit_breaker_response_time_ms{breaker="coincap"} 125.5

# System-wide metrics
cryptovault_system_uptime_percentage 99.8
```

## Usage Examples

### Example 1: Protected Price Fetching

```python
from circuit_breaker import with_circuit_breaker, BREAKER_COINCAP

@with_circuit_breaker(breaker=BREAKER_COINCAP, fallback_func=lambda *args, **kwargs: [])
async def get_crypto_prices():
    """Returns [] if CoinCap API is down"""
    # Your API call here
    return prices

# Usage
prices = await get_crypto_prices()
if not prices:
    logger.warning("CoinCap API unavailable, using cached prices")
    prices = await get_cached_prices()
```

### Example 2: Protected Email Sending

```python
from circuit_breaker import with_circuit_breaker, BREAKER_EMAIL

@with_circuit_breaker(breaker=BREAKER_EMAIL, fallback_func=lambda *args, **kwargs: False)
async def send_notification_email(user_email, subject, body):
    """Returns False if email provider is down"""
    return await email_provider.send(user_email, subject, body)

# Usage
success = await send_notification_email(email, "Alert", "Price dropped")
if not success:
    # Store for retry or use alternative notification method
    await store_notification_for_retry(email, subject, body)
```

### Example 3: Manual Breaker Checking

```python
from circuit_breaker import BREAKER_TELEGRAM

if BREAKER_TELEGRAM.is_available():
    await notify_admin_telegram("New deposit received")
else:
    logger.info("Telegram API unavailable, skipping notification")
    # Fall back to email or store for later
```

## Deployment Checklist

- [ ] Circuit breakers initialized in server startup (see `server.py` lifespan)
- [ ] All external API calls decorated with `@with_circuit_breaker`
- [ ] Fallback functions provided for each breaker
- [ ] Monitoring endpoints exposed (`/api/admin/circuit-breakers`)
- [ ] Prometheus metrics scraped by monitoring system
- [ ] Alerts configured for `system_status == "CRITICAL"`
- [ ] Runbook prepared for manual breaker reset (`POST /api/admin/circuit-breakers/reset/{name}`)

## Troubleshooting

### Circuit Breaker Always Open

**Symptom**: Service always returns fallback value, never attempts real API call

**Causes**:
- External service genuinely unavailable (check service status)
- Very low failure threshold configured
- Timeout too short to allow service recovery

**Solution**:
```python
# Check breaker state
registry = CircuitBreakerRegistry.get_instance()
breaker = registry.get("coincap")
print(f"State: {breaker.state}")
print(f"Failures: {breaker.failure_count}")
print(f"Time until next recovery: {breaker.get_time_until_recovery()}")

# Manual reset (admin only)
POST /api/admin/circuit-breakers/reset/coincap
```

### Circuit Breaker Too Sensitive (Opens Too Quickly)

**Symptom**: Breaker opens too quickly during temporary outages

**Solution**:
```python
# Increase failure threshold
breaker.failure_threshold = 10  # Require 10 failures to open

# Increase timeout for recovery
breaker.timeout_seconds = 300  # Wait 5 minutes before trying recovery
```

### Monitoring Shows High Failure Rate

**Symptom**: Dashboard shows high failure percentage but service seems to be working

**Causes**:
- Transient network issues fixed by retry logic
- Expected failures (auth errors) being counted

**Solution**:
- Review metrics over time (single spike vs. sustained trend)
- Check if failures are decreasing (system recovering)
- Distinguish between transient and persistent failures

## Best Practices

1. **Always Provide Fallback**: Every decorator must have a `fallback_func`
2. **Monitor Metrics**: Track breaker states, not just application logs
3. **Alert on CRITICAL**: Configure alerts for `system_status == "CRITICAL"`
4. **Document Fallback Behavior**: Make it clear what happens when a service is down
5. **Test Recovery**: Periodically test that HALF_OPEN state successfully recovers
6. **Log State Changes**: All state transitions are logged at WARNING level
7. **Use Consistent Thresholds**: Similar services should have similar settings
8. **Don't Override Too Frequently**: Manual resets should be rare

## Related Documentation

- [Request Retry Logic](RETRY_LOGIC.md) - Handles transient failures with exponential backoff
- [Performance Monitoring](MONITORING.md) - Tracks request timing and performance
- [API Response Caching](CACHING.md) - Reduces dependency on external APIs
- [Database Query Optimization](QUERY_OPTIMIZATION.md) - Reduces internal API load

## Support

For circuit breaker issues:
1. Check `/api/admin/circuit-breakers` dashboard
2. Review logs for state change messages
3. Verify external service is accessible
4. Check Prometheus metrics for trends
5. Contact DevOps if manual intervention needed
