"""
Monitoring and Metrics Endpoints
Prometheus-compatible metrics and health checks
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from datetime import datetime
import psutil
import asyncio
from typing import Dict, Any
import logging

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ============================================
# METRICS TRACKING
# ============================================

class MetricsCollector:
    """Simple metrics collector"""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.request_duration_sum = 0.0
        self.started_at = datetime.now(timezone.utc)
    
    def record_request(self, duration_ms: float, is_error: bool = False):
        """Record a request"""
        self.request_count += 1
        self.request_duration_sum += duration_ms
        if is_error:
            self.error_count += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        avg_duration = (
            self.request_duration_sum / self.request_count 
            if self.request_count > 0 else 0
        )
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0,
            "avg_response_time_ms": avg_duration
        }


# Global metrics collector
metrics = MetricsCollector()


# ============================================
# ENDPOINTS
# ============================================

@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe
    Returns 200 if application is alive
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe
    Returns 200 if application is ready to serve traffic
    """
    # Check if critical services are available
    ready = True
    services = {}
    
    # Check database (quick test)
    try:
        # This should be replaced with actual database check
        services["database"] = "ready"
    except Exception as e:
        services["database"] = f"not ready: {str(e)}"
        ready = False
    
    status_code = 200 if ready else 503
    
    response_data = {
        "status": "ready" if ready else "not ready",
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return JSONResponse(
        content=response_data,
        status_code=status_code
    )


@router.get("/metrics")
async def get_metrics():
    """
    Prometheus-compatible metrics endpoint
    """
    app_metrics = metrics.get_metrics()
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Format as Prometheus metrics
    prometheus_format = f"""
# HELP cryptovault_uptime_seconds Application uptime in seconds
# TYPE cryptovault_uptime_seconds gauge
cryptovault_uptime_seconds {app_metrics['uptime_seconds']}

# HELP cryptovault_requests_total Total number of requests
# TYPE cryptovault_requests_total counter
cryptovault_requests_total {app_metrics['total_requests']}

# HELP cryptovault_errors_total Total number of errors
# TYPE cryptovault_errors_total counter
cryptovault_errors_total {app_metrics['total_errors']}

# HELP cryptovault_error_rate Error rate (errors/requests)
# TYPE cryptovault_error_rate gauge
cryptovault_error_rate {app_metrics['error_rate']}

# HELP cryptovault_response_time_avg_ms Average response time in milliseconds
# TYPE cryptovault_response_time_avg_ms gauge
cryptovault_response_time_avg_ms {app_metrics['avg_response_time_ms']}

# HELP cryptovault_cpu_percent CPU usage percentage
# TYPE cryptovault_cpu_percent gauge
cryptovault_cpu_percent {cpu_percent}

# HELP cryptovault_memory_percent Memory usage percentage
# TYPE cryptovault_memory_percent gauge
cryptovault_memory_percent {memory.percent}

# HELP cryptovault_disk_percent Disk usage percentage
# TYPE cryptovault_disk_percent gauge
cryptovault_disk_percent {disk.percent}
"""
    
    return Response(content=prometheus_format.strip(), media_type="text/plain")


@router.get("/metrics/json")
async def get_metrics_json():
    """
    JSON metrics endpoint
    """
    app_metrics = metrics.get_metrics()
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application": app_metrics,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024 * 1024 * 1024)
        }
    }


@router.get("/circuit-breakers")
async def get_circuit_breakers():
    """
    Get circuit breaker states
    """
    try:
        from services.circuit_breaker import get_all_breakers
        return get_all_breakers()
    except ImportError:
        return {"error": "Circuit breakers not available"}


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str):
    """
    Manually reset a circuit breaker
    """
    try:
        from services.circuit_breaker import reset_breaker
        success = await reset_breaker(name)
        if success:
            return {"message": f"Circuit breaker '{name}' reset successfully"}
        else:
            return {"error": f"Circuit breaker '{name}' not found"}
    except ImportError:
        return {"error": "Circuit breakers not available"}


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check for all services.
    Returns comprehensive status of database, cache, external APIs, and Socket.IO.
    
    Use Cases:
    - Production monitoring dashboards
    - Zero-downtime deployment verification
    - Service dependency validation
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "version": settings.app_version,
        "services": {}
    }
    
    errors = []
    
    # 1. Database Health
    try:
        from dependencies import get_db_connection
        db_conn = get_db_connection()
        if db_conn and db_conn.is_connected:
            # Quick ping test with timeout
            await asyncio.wait_for(db_conn.health_check(), timeout=2.0)
            health["services"]["database"] = {
                "status": "healthy",
                "type": "mongodb",
                "pool_size": settings.mongo_max_pool_size
            }
        else:
            health["services"]["database"] = {"status": "degraded", "error": "Not connected"}
            errors.append("database")
    except asyncio.TimeoutError:
        health["services"]["database"] = {"status": "degraded", "error": "Timeout"}
        errors.append("database")
    except Exception as e:
        health["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        errors.append("database")
    
    # 2. Redis Cache Health
    try:
        from redis_cache import redis_cache
        if redis_cache.use_redis:
            # Test Redis connection
            test_key = "health_check_test"
            await redis_cache.set(test_key, "ok", ttl=5)
            result = await redis_cache.get(test_key)
            
            if result == "ok":
                health["services"]["redis"] = {
                    "status": "healthy",
                    "type": "upstash_redis",
                    "mode": "redis"
                }
            else:
                health["services"]["redis"] = {"status": "degraded", "error": "Read/write test failed"}
        else:
            health["services"]["redis"] = {
                "status": "healthy",
                "type": "in_memory",
                "mode": "fallback"
            }
    except Exception as e:
        health["services"]["redis"] = {"status": "degraded", "error": str(e), "mode": "fallback"}
    
    # 3. Socket.IO Health
    try:
        from socketio_server import socketio_manager
        stats = socketio_manager.get_stats()
        health["services"]["socketio"] = {
            "status": "healthy",
            "connections": stats.get("total_connections", 0),
            "authenticated_users": stats.get("authenticated_users", 0)
        }
    except Exception as e:
        health["services"]["socketio"] = {"status": "degraded", "error": str(e)}
    
    # 4. Price Feed Health
    try:
        from services import price_stream_service
        price_status = price_stream_service.get_status()
        health["services"]["price_feed"] = {
            "status": "healthy" if price_status.get("enabled") else "disabled",
            "state": price_status.get("state", "unknown"),
            "source": price_status.get("source", "unknown"),
            "prices_cached": len(price_stream_service.prices)
        }
    except Exception as e:
        health["services"]["price_feed"] = {"status": "degraded", "error": str(e)}
    
    # 5. Email Service Health
    try:
        from email_service import email_service
        health["services"]["email"] = {
            "status": "healthy",
            "mode": email_service.mode,
            "provider": email_service.mode
        }
    except Exception as e:
        health["services"]["email"] = {"status": "degraded", "error": str(e)}
    
    # 6. Sentry Health
    if settings.is_sentry_available():
        health["services"]["sentry"] = {
            "status": "healthy",
            "environment": settings.environment,
            "sample_rate": settings.sentry_traces_sample_rate
        }
    else:
        health["services"]["sentry"] = {"status": "disabled"}
    
    # 7. System Resources
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health["system"] = {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_available_mb": round(memory.available / (1024 * 1024), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
        }
        
        # Flag if resources are low
        if cpu > 90 or memory.percent > 90 or disk.percent > 90:
            errors.append("system_resources")
            health["system"]["warning"] = "High resource usage detected"
    except Exception as e:
        health["system"] = {"error": str(e)}
    
    # Determine overall status
    if len(errors) == 0:
        health["status"] = "healthy"
    elif "database" in errors:
        health["status"] = "unhealthy"
    else:
        health["status"] = "degraded"
    
    status_code = 200 if health["status"] == "healthy" else (503 if health["status"] == "unhealthy" else 200)
    
    return JSONResponse(content=health, status_code=status_code)
