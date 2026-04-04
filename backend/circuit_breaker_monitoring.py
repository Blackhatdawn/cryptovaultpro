"""
Circuit Breaker Monitoring & Metrics
Provides real-time visibility into circuit breaker health and performance
Phase 3: Advanced resilience monitoring
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

from circuit_breaker import CircuitBreakerRegistry, CircuitState

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerMetrics:
    """Metrics for a single circuit breaker"""
    name: str
    state: str  # "CLOSED", "OPEN", "HALF_OPEN"
    success_count: int
    failure_count: int
    request_count: int
    last_failure_time: Optional[str]
    last_success_time: Optional[str]
    uptime_percentage: float
    average_response_time_ms: float
    last_state_change_time: Optional[str]
    time_to_next_recovery_attempt_s: Optional[float]
    configured_failure_threshold: int
    configured_timeout_seconds: int


class CircuitBreakerMonitor:
    """Monitor and collect metrics from all circuit breakers"""
    
    def __init__(self):
        self.registry = CircuitBreakerRegistry.get_instance()
        self.start_time = datetime.now(timezone.utc)
        self._metrics_history: Dict[str, List[Dict[str, Any]]] = {}
        
    def get_all_breaker_metrics(self) -> List[CircuitBreakerMetrics]:
        """Get current metrics for all circuit breakers"""
        metrics = []
        for breaker_name, breaker in self.registry.breakers.items():
            metrics.append(self._get_breaker_metrics(breaker_name, breaker))
        return metrics
    
    def get_breaker_metrics(self, breaker_name: str) -> Optional[CircuitBreakerMetrics]:
        """Get metrics for a specific circuit breaker"""
        if breaker_name not in self.registry.breakers:
            return None
        breaker = self.registry.breakers[breaker_name]
        return self._get_breaker_metrics(breaker_name, breaker)
    
    def _get_breaker_metrics(self, name: str, breaker) -> CircuitBreakerMetrics:
        """Calculate metrics for a single breaker"""
        total_requests = breaker.success_count + breaker.failure_count
        uptime = 100.0 if total_requests == 0 else (breaker.success_count / total_requests) * 100
        
        # Calculate average response time
        if breaker.response_times:
            avg_response_time = sum(breaker.response_times) / len(breaker.response_times) * 1000
        else:
            avg_response_time = 0.0
        
        # Time to recovery
        time_to_recovery = None
        if breaker.state == CircuitState.OPEN:
            time_since_open = time.time() - breaker.opened_at if breaker.opened_at else 0
            time_to_recovery = max(0, breaker.timeout_seconds - time_since_open)
        
        return CircuitBreakerMetrics(
            name=name,
            state=breaker.state.value.upper(),
            success_count=breaker.success_count,
            failure_count=breaker.failure_count,
            request_count=total_requests,
            last_failure_time=breaker.last_failure_time.isoformat() if breaker.last_failure_time else None,
            last_success_time=breaker.last_success_time.isoformat() if breaker.last_success_time else None,
            uptime_percentage=round(uptime, 2),
            average_response_time_ms=round(avg_response_time, 2),
            last_state_change_time=breaker.last_state_change_time.isoformat() if breaker.last_state_change_time else None,
            time_to_next_recovery_attempt_s=round(time_to_recovery, 2) if time_to_recovery is not None else None,
            configured_failure_threshold=breaker.failure_threshold,
            configured_timeout_seconds=breaker.timeout_seconds
        )
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get overall system health status"""
        metrics = self.get_all_breaker_metrics()
        
        closed_count = sum(1 for m in metrics if m.state == "CLOSED")
        open_count = sum(1 for m in metrics if m.state == "OPEN")
        half_open_count = sum(1 for m in metrics if m.state == "HALF_OPEN")
        
        total_requests = sum(m.request_count for m in metrics)
        total_success = sum(m.success_count for m in metrics)
        overall_uptime = 100.0 if total_requests == 0 else (total_success / total_requests) * 100
        
        # Identify failing services
        failing_services = [m.name for m in metrics if m.state == "OPEN"]
        recovering_services = [m.name for m in metrics if m.state == "HALF_OPEN"]
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_uptime_percentage": round(overall_uptime, 2),
            "breaker_states": {
                "closed": closed_count,
                "open": open_count,
                "half_open": half_open_count,
                "total": len(metrics)
            },
            "total_requests": total_requests,
            "total_successful_requests": total_success,
            "total_failed_requests": sum(m.failure_count for m in metrics),
            "failing_services": failing_services,
            "recovering_services": recovering_services,
            "system_status": "HEALTHY" if open_count == 0 else "DEGRADED" if open_count == 1 else "CRITICAL"
        }
    
    def get_breaker_history(self, breaker_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent state change history for a breaker"""
        if breaker_name not in self._metrics_history:
            return []
        return self._metrics_history[breaker_name][-limit:]
    
    def record_state_change(self, breaker_name: str, old_state: str, new_state: str, reason: str = ""):
        """Record a circuit breaker state change"""
        if breaker_name not in self._metrics_history:
            self._metrics_history[breaker_name] = []
        
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason
        }
        self._metrics_history[breaker_name].append(record)
        
        logger.info(
            f"🔄 Circuit breaker {breaker_name}: {old_state} → {new_state} ({reason})"
        )
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        metrics = self.get_all_breaker_metrics()
        summary = self.get_system_health_summary()
        
        lines = []
        lines.append("# HELP cryptovault_circuit_breaker_state Current state of circuit breaker (1=CLOSED, 2=OPEN, 3=HALF_OPEN)")
        lines.append("# TYPE cryptovault_circuit_breaker_state gauge")
        
        state_map = {"CLOSED": 1, "OPEN": 2, "HALF_OPEN": 3}
        for metric in metrics:
            state_value = state_map.get(metric.state, 0)
            lines.append(f'cryptovault_circuit_breaker_state{{breaker="{metric.name}"}} {state_value}')
        
        lines.append("")
        lines.append("# HELP cryptovault_circuit_breaker_requests_total Total requests handled by circuit breaker")
        lines.append("# TYPE cryptovault_circuit_breaker_requests_total counter")
        for metric in metrics:
            lines.append(f'cryptovault_circuit_breaker_requests_total{{breaker="{metric.name}"}} {metric.request_count}')
        
        lines.append("")
        lines.append("# HELP cryptovault_circuit_breaker_failures_total Total failures recorded by circuit breaker")
        lines.append("# TYPE cryptovault_circuit_breaker_failures_total counter")
        for metric in metrics:
            lines.append(f'cryptovault_circuit_breaker_failures_total{{breaker="{metric.name}"}} {metric.failure_count}')
        
        lines.append("")
        lines.append("# HELP cryptovault_circuit_breaker_uptime_percentage Current uptime percentage")
        lines.append("# TYPE cryptovault_circuit_breaker_uptime_percentage gauge")
        for metric in metrics:
            lines.append(f'cryptovault_circuit_breaker_uptime_percentage{{breaker="{metric.name}"}} {metric.uptime_percentage}')
        
        lines.append("")
        lines.append("# HELP cryptovault_circuit_breaker_response_time_ms Average response time in milliseconds")
        lines.append("# TYPE cryptovault_circuit_breaker_response_time_ms gauge")
        for metric in metrics:
            lines.append(f'cryptovault_circuit_breaker_response_time_ms{{breaker="{metric.name}"}} {metric.average_response_time_ms}')
        
        lines.append("")
        lines.append("# HELP cryptovault_system_uptime_percentage System-wide uptime percentage")
        lines.append("# TYPE cryptovault_system_uptime_percentage gauge")
        lines.append(f'cryptovault_system_uptime_percentage {summary["system_uptime_percentage"]}')
        
        return "\n".join(lines)


# Global singleton monitor
circuit_breaker_monitor = CircuitBreakerMonitor()
