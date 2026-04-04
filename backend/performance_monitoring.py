"""
Web Vitals & Performance Monitoring
Tracks Core Web Vitals and backend performance metrics
Integration with Sentry for error tracking
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MetricStatus(Enum):
    """Web Vitals status classification"""
    GOOD = "good"          # < threshold
    NEEDS_IMPROVEMENT = "needs-improvement"  # Between good and poor
    POOR = "poor"          # > threshold


@dataclass
class CoreWebVital:
    """Tracks individual Core Web Vital metric"""
    name: str
    value: float  # Milliseconds or context-specific unit
    threshold_good: float
    threshold_poor: float
    unit: str = "ms"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    @property
    def status(self) -> MetricStatus:
        """Classify metric status"""
        if self.value <= self.threshold_good:
            return MetricStatus.GOOD
        elif self.value <= self.threshold_poor:
            return MetricStatus.NEEDS_IMPROVEMENT
        else:
            return MetricStatus.POOR
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }


class PerformanceMetrics:
    """Collect and track performance metrics"""
    
    # Web Vitals thresholds (from Google)
    # LCP (Largest Contentful Paint): < 2.5s good, < 4s needs improvement
    # FID (First Input Delay): < 100ms good, < 300ms needs improvement
    # CLS (Cumulative Layout Shift): < 0.1 good, < 0.25 needs improvement
    
    VITALS_THRESHOLDS = {
        "lcp": {"good": 2500, "poor": 4000},     # milliseconds
        "fid": {"good": 100, "poor": 300},       # milliseconds
        "cls": {"good": 0.1, "poor": 0.25},      # unitless
        "ttfb": {"good": 600, "poor": 1800},     # Time to First Byte
        "fp": {"good": 1000, "poor": 3000},      # First Paint
        "fcp": {"good": 1800, "poor": 3000},     # First Contentful Paint
    }
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.api_timings: Dict[str, list] = {}
        self.error_count = 0
        self.last_collection_time = datetime.utcnow()
        self.collection_interval = timedelta(hours=1)
    
    def record_vital(
        self,
        name: str,
        value: float,
        session_id: Optional[str] = None,
    ) -> CoreWebVital:
        """
        Record Core Web Vital measurement.
        
        Args:
            name: Vital name (lcp, fid, cls, ttfb, fp, fcp)
            value: Metric value
            session_id: User session identifier
        
        Returns:
            CoreWebVital object
        """
        
        thresholds = self.VITALS_THRESHOLDS.get(name, {"good": 0, "poor": 0})
        
        vital = CoreWebVital(
            name=name,
            value=value,
            threshold_good=thresholds["good"],
            threshold_poor=thresholds["poor"],
        )
        
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append(vital)
        
        # Log warning if performance is poor
        if vital.status == MetricStatus.POOR:
            logger.warning(
                f"⚠️  POOR Core Web Vital: {name}={value} "
                f"(threshold: {thresholds['poor']})"
            )
        
        elif vital.status == MetricStatus.NEEDS_IMPROVEMENT:
            logger.info(
                f"ℹ️  Core Web Vital needs improvement: {name}={value}"
            )
        
        return vital
    
    def record_api_timing(
        self,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: int,
        success: bool = True,
    ) -> None:
        """
        Record API endpoint performance.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
            success: Whether request succeeded
        """
        
        key = f"{method} {endpoint}"
        
        if key not in self.api_timings:
            self.api_timings[key] = []
        
        self.api_timings[key].append({
            "response_time_ms": response_time_ms,
            "status_code": status_code,
            "success": success,
            "timestamp": datetime.utcnow(),
        })
        
        # Alert on slow API calls (> 1000ms)
        if response_time_ms > 1000:
            logger.warning(
                f"🐌 SLOW API: {key} took {response_time_ms}ms "
                f"(HTTP {status_code})"
            )
    
    def record_error(self, error_type: str) -> None:
        """Record error occurrence"""
        self.error_count += 1
        logger.error(f"❌ Error recorded: {error_type}")
    
    def get_vital_stats(self, name: str) -> Optional[dict]:
        """Get statistics for specific vital"""
        if name not in self.metrics or not self.metrics[name]:
            return None
        
        values = [m.value for m in self.metrics[name]]
        
        return {
            "name": name,
            "count": len(values),
            "average": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "status": self.metrics[name][-1].status.value,
            "unit": self.metrics[name][0].unit,
        }
    
    def get_api_stats(self, endpoint: Optional[str] = None) -> dict:
        """Get API performance statistics"""
        stats = {}
        
        for key, timings in self.api_timings.items():
            if endpoint and endpoint not in key:
                continue
            
            response_times = [t["response_time_ms"] for t in timings]
            successful = sum(1 for t in timings if t["success"])
            
            stats[key] = {
                "calls": len(timings),
                "successful": successful,
                "failed": len(timings) - successful,
                "success_rate": successful / len(timings) if timings else 0,
                "avg_response_ms": sum(response_times) / len(response_times),
                "min_response_ms": min(response_times),
                "max_response_ms": max(response_times),
            }
        
        return stats
    
    def get_summary(self) -> dict:
        """Get overall performance summary"""
        
        vitals_summary = {}
        for vital_name in self.VITALS_THRESHOLDS.keys():
            stats = self.get_vital_stats(vital_name)
            if stats:
                vitals_summary[vital_name] = stats
        
        api_summary = self.get_api_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "core_web_vitals": vitals_summary,
            "api_performance": api_summary,
            "error_count": self.error_count,
            "total_recorded_vitals": sum(len(v) for v in self.metrics.values()),
            "total_api_calls": sum(len(t) for t in self.api_timings.values()),
        }
    
    def reset(self) -> None:
        """Reset all metrics"""
        self.metrics.clear()
        self.api_timings.clear()
        self.error_count = 0
        logger.info("🔄 Performance metrics reset")


class RequestTimer:
    """Context manager for timing requests"""
    
    def __init__(self, name: str, logger_func=logger.info):
        self.name = name
        self.logger_func = logger_func
        self.start_time = None
        self.elapsed_ms = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            logger.error(
                f"❌ {self.name} failed after {self.elapsed_ms:.2f}ms: {exc_val}"
            )
        else:
            if self.elapsed_ms > 1000:
                logger.warning(f"🐌 {self.name}: {self.elapsed_ms:.2f}ms")
            else:
                self.logger_func(f"✅ {self.name}: {self.elapsed_ms:.2f}ms")


# Global performance metrics instance
performance_metrics = PerformanceMetrics()


def send_metrics_to_sentry(summary: dict) -> None:
    """
    Send performance metrics to Sentry for monitoring.
    Should be called periodically (e.g., hourly).
    
    Args:
        summary: Summary dict from performance_metrics.get_summary()
    """
    try:
        import sentry_sdk
        
        # Set performance tags
        sentry_sdk.capture_event({
            "type": "transaction",
            "transaction": "performance-metrics",
            "contexts": {
                "performance": summary,
            },
            "level": "info",
            "message": "Performance metrics snapshot",
        })
        
        logger.info("📊 Sent performance metrics to Sentry")
    
    except Exception as e:
        logger.warning(f"Could not send metrics to Sentry: {str(e)}")


# Export frontend monitoring initialization
FRONTEND_MONITORING_SCRIPT = """
<script type="module">
// Initialize Web Vitals monitoring
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

// Send metrics to backend
async function sendMetric(name, value) {
    try {
        await fetch('/api/metrics/vitals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, value })
        });
    } catch (e) {
        console.warn('Could not send metric:', e);
    }
}

getCLS(metric => sendMetric('cls', metric.value));
getFID(metric => sendMetric('fid', metric.value));
getFCP(metric => sendMetric('fcp', metric.value));
getLCP(metric => sendMetric('lcp', metric.value));
getTTFB(metric => sendMetric('ttfb', metric.value));
</script>
"""
