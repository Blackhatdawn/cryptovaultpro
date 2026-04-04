# Circuit Breaker Quick Reference

## 1-Minute Setup

```python
from circuit_breaker import with_circuit_breaker, BREAKER_COINCAP

# Protect any async function
@with_circuit_breaker(breaker=BREAKER_COINCAP, fallback_func=lambda *args, **kwargs: [])
async def get_prices():
    return await expensive_api_call()

# When API fails: returns [] immediately (no timeout)
prices = await get_prices()
```

## Monitoring Endpoints

```bash
# View all breakers
curl http://localhost:8000/api/admin/circuit-breakers

# View specific breaker
curl http://localhost:8000/api/admin/circuit-breakers/coincap

# System health
curl http://localhost:8000/api/admin/health/circuit-breakers

# Prometheus metrics
curl http://localhost:8000/api/admin/metrics

# State history
curl http://localhost:8000/api/admin/circuit-breakers/coincap/history

# Reset breaker (admin only)
curl -X GET http://localhost:8000/api/admin/circuit-breakers/reset/coincap
```

## State Diagram

```
CLOSED → failures >= threshold → OPEN
OPEN → timeout elapsed → HALF_OPEN → success → CLOSED (or failure → OPEN)
```

## Five Protected Services

| Service | Breaker | Import | Fallback |
|---------|---------|--------|----------|
| CoinGecko Prices | `BREAKER_COINCAP` | `from circuit_breaker import BREAKER_COINCAP` | `[]` |
| Telegram Notifications | `BREAKER_TELEGRAM` | `from circuit_breaker import BREAKER_TELEGRAM` | `False` |
| NowPayments | `BREAKER_NOWPAYMENTS` | `from circuit_breaker import BREAKER_NOWPAYMENTS` | `{"error": "..."}` |
| Firebase/FCM | `BREAKER_FIREBASE` | `from circuit_breaker import BREAKER_FIREBASE` | Mock response |
| Email (SendGrid/SMTP) | `BREAKER_EMAIL` | `from circuit_breaker import BREAKER_EMAIL` | `False` |

## Common Patterns

### Pattern 1: API Call with Fallback
```python
if BREAKER_COINCAP.is_available():
    prices = await fetch_live_prices()
else:
    prices = await get_cached_prices()
```

### Pattern 2: Decorated Function
```python
@with_circuit_breaker(breaker=BREAKER_TELEGRAM, fallback_func=lambda *args, **kwargs: False)
async def send_alert(message):
    await telegram_api.send(message)
    return True
```

### Pattern 3: Manual Error Handling
```python
try:
    if not BREAKER_EMAIL.is_available():
        raise ServiceUnavailableError("Email service unavailable")
    await send_email(...)
except ServiceUnavailableError:
    await store_for_later_delivery(...)
```

## Debugging

```python
from circuit_breaker import CircuitBreakerRegistry

registry = CircuitBreakerRegistry.get_instance()
breaker = registry.get("coincap")

# Current state
print(f"State: {breaker.state}")  # CLOSED, OPEN, or HALF_OPEN

# Statistics
print(f"Success: {breaker.success_count}")
print(f"Failures: {breaker.failure_count}")
print(f"Total: {breaker.success_count + breaker.failure_count}")

# Configuration
print(f"Threshold: {breaker.failure_threshold}")
print(f"Timeout: {breaker.timeout_seconds}s")

# Time tracking
print(f"Last failure: {breaker.last_failure_time}")
print(f"Last success: {breaker.last_success_time}")
```

## Status Indicators

```json
{
  "HEALTHY": "All breakers CLOSED, 100% uptime",
  "DEGRADED": "1 breaker OPEN, 95-99% uptime",
  "CRITICAL": "2+ breakers OPEN, <95% uptime"
}
```

## Environment Variables

None required - circuit breakers are auto-configured. Optional:

```bash
# Adjust via code only (no env vars for security)
CIRCUIT_BREAKER_COINCAP_THRESHOLD=10
CIRCUIT_BREAKER_COINCAP_TIMEOUT=120
```

## Testing

```python
import pytest
from circuit_breaker import CircuitBreaker

def test_breaker_opens():
    breaker = CircuitBreaker("test", failure_threshold=2)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

# Run tests
pytest tests/test_circuit_breaker.py -v
pytest tests/test_circuit_breaker_integration.py -v
```

## Real Examples in Codebase

- **coincap_service.py** - Line 66: `_fetch_real_prices()`
- **email_service.py** - Lines 399, 446, 505: Email send methods
- **fcm_service.py** - Lines 74, 117: Notification methods
- **nowpayments_service.py** - Lines 63, 132: Payment methods
- **telegram_bot.py** - Line 50: `send_message()`

## Logs to Watch

```
🔄 Circuit breaker coincap: CLOSED → OPEN (5 failures)
⏱️ Circuit breaker coincap: HALF_OPEN (testing recovery)
✅ Circuit breaker coincap: HALF_OPEN → CLOSED (recovered)
🔧 Circuit breaker coincap manually reset by admin
```

## Performance Impact

- **Breaker Check**: < 1ms (in-memory state check)
- **Success Recording**: < 1ms
- **Failure Recording**: < 1ms
- **Fallback Invocation**: Depends on fallback function
- **Monitoring Dashboard**: < 50ms (aggregates 5 breakers)

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Breaker always open | Service down | Check service, or reset breaker |
| Too many fallbacks | Low threshold | Increase `failure_threshold` |
| Slow recovery | Long timeout | Decrease `timeout_seconds` |
| Can't reset | No admin perms | Use authenticated admin endpoint |
| No metrics | Monitoring not running | Check `/api/admin/metrics` endpoint |

## Related Files

- `backend/circuit_breaker.py` - Core implementation
- `backend/circuit_breaker_monitoring.py` - Metrics & monitoring
- `backend/routers/circuit_breaker_monitor.py` - API endpoints
- `tests/test_circuit_breaker.py` - Unit tests
- `tests/test_circuit_breaker_integration.py` - Integration tests
- `CIRCUIT_BREAKER_GUIDE.md` - Full documentation

## Next Steps

1. ✅ Core circuit breaker implementation
2. ✅ Integration with 5 services
3. ✅ Monitoring dashboard
4. ✅ Metrics & prometheus export
5. ✅ Test suite
6. ✅ Documentation

**Deployment Status**: Ready for production! 🚀
