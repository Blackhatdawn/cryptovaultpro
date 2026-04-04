"""
Circuit Breaker Monitor API Router
Provides REST endpoints for monitoring circuit breaker health and metrics
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from circuit_breaker_monitoring import circuit_breaker_monitor, CircuitBreakerMetrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["monitoring"])


@router.get(
    "/circuit-breakers",
    response_model=List[Dict[str, Any]],
    summary="Get all circuit breaker states",
    description="Returns current state and metrics for all circuit breakers"
)
async def get_all_circuit_breakers():
    """
    Get metrics for all circuit breakers.
    
    Returns state, uptime, request counts, and recovery information for each breaker.
    """
    try:
        metrics = circuit_breaker_monitor.get_all_breaker_metrics()
        return [
            {
                "name": m.name,
                "state": m.state,
                "uptime_percentage": m.uptime_percentage,
                "request_count": m.request_count,
                "success_count": m.success_count,
                "failure_count": m.failure_count,
                "average_response_time_ms": m.average_response_time_ms,
                "last_state_change_time": m.last_state_change_time,
                "time_to_next_recovery_attempt_s": m.time_to_next_recovery_attempt_s,
                "failure_threshold": m.configured_failure_threshold,
                "timeout_seconds": m.configured_timeout_seconds,
            }
            for m in metrics
        ]
    except Exception as e:
        logger.error(f"Error fetching circuit breaker metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


@router.get(
    "/circuit-breakers/{breaker_name}",
    response_model=Dict[str, Any],
    summary="Get specific circuit breaker metrics",
    description="Returns detailed metrics for a single circuit breaker"
)
async def get_circuit_breaker(breaker_name: str):
    """
    Get detailed metrics for a specific circuit breaker.
    
    - **breaker_name**: Name of the circuit breaker (coincap, telegram, firebase, nowpayments, email)
    """
    try:
        metric = circuit_breaker_monitor.get_breaker_metrics(breaker_name)
        if not metric:
            raise HTTPException(
                status_code=404, 
                detail=f"Circuit breaker '{breaker_name}' not found"
            )
        
        return {
            "name": metric.name,
            "state": metric.state,
            "uptime_percentage": metric.uptime_percentage,
            "request_count": metric.request_count,
            "success_count": metric.success_count,
            "failure_count": metric.failure_count,
            "average_response_time_ms": metric.average_response_time_ms,
            "last_failure_time": metric.last_failure_time,
            "last_success_time": metric.last_success_time,
            "last_state_change_time": metric.last_state_change_time,
            "time_to_next_recovery_attempt_s": metric.time_to_next_recovery_attempt_s,
            "failure_threshold": metric.configured_failure_threshold,
            "timeout_seconds": metric.configured_timeout_seconds,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching breaker metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


@router.get(
    "/circuit-breakers/{breaker_name}/history",
    response_model=List[Dict[str, Any]],
    summary="Get circuit breaker state change history",
    description="Returns recent state transitions for a circuit breaker"
)
async def get_circuit_breaker_history(
    breaker_name: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get recent state change history for a circuit breaker.
    
    - **breaker_name**: Name of the circuit breaker
    - **limit**: Maximum number of history entries to return (default: 100, max: 1000)
    """
    try:
        history = circuit_breaker_monitor.get_breaker_history(breaker_name, limit)
        if not history and breaker_name not in circuit_breaker_monitor.registry.breakers:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker '{breaker_name}' not found"
            )
        return history
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching breaker history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.get(
    "/health/circuit-breakers",
    response_model=Dict[str, Any],
    summary="Get system health overview",
    description="Returns overall system health based on circuit breaker states"
)
async def get_system_health_overview():
    """
    Get overall system health based on circuit breaker states.
    
    Returns:
    - System uptime percentage
    - Breaker state counts (closed, open, half-open)
    - List of failing services
    - System status (HEALTHY, DEGRADED, CRITICAL)
    """
    try:
        summary = circuit_breaker_monitor.get_system_health_summary()
        return summary
    except Exception as e:
        logger.error(f"Error calculating system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate health")


@router.get(
    "/metrics",
    summary="Get Prometheus metrics",
    description="Returns metrics in Prometheus format for scraping"
)
async def get_prometheus_metrics():
    """
    Get circuit breaker metrics in Prometheus text format.
    
    Includes:
    - Breaker states (1=CLOSED, 2=OPEN, 3=HALF_OPEN)
    - Total requests per breaker
    - Total failures per breaker
    - Uptime percentages
    - Average response times
    - System-wide uptime
    """
    try:
        metrics_text = circuit_breaker_monitor.export_prometheus_metrics()
        return {
            "content": metrics_text,
            "content_type": "text/plain; version=0.0.4"
        }
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")


@router.get(
    "/circuit-breakers/reset/{breaker_name}",
    summary="Reset circuit breaker",
    description="Force a circuit breaker to CLOSED state (admin only)"
)
async def reset_circuit_breaker(breaker_name: str):
    """
    Reset a circuit breaker to CLOSED state.
    
    ⚠️ Admin action: Use with caution, only affects the named breaker.
    """
    try:
        registry = circuit_breaker_monitor.registry
        if breaker_name not in registry.breakers:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker '{breaker_name}' not found"
            )
        
        breaker = registry.breakers[breaker_name]
        old_state = breaker.state.value
        breaker.reset()
        new_state = breaker.state.value
        
        circuit_breaker_monitor.record_state_change(
            breaker_name,
            old_state,
            new_state,
            reason="Admin reset"
        )
        
        logger.warning(f"🔧 Circuit breaker {breaker_name} manually reset by admin")
        
        return {
            "breaker": breaker_name,
            "action": "reset",
            "old_state": old_state,
            "new_state": new_state,
            "message": f"Circuit breaker {breaker_name} has been reset to CLOSED state"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting breaker: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset breaker")
