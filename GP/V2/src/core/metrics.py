from dataclasses import dataclass, field
from typing import Any, Optional
import time

@dataclass(kw_only=True)
class LogEvent:
    """
    Base class for all loggable events in the system

      to accurately measure durations and sequence of events
    """
    run_id: int
    subsystem: str
    ts: float = field(default_factory=time.time)
    ts_mono: float = field(default_factory=time.perf_counter)

@dataclass(kw_only=True)
class TickEvent(LogEvent):
    """
    Records the timing of an subsystem work cycle.
    
    Metrics
    - Latency:
    - Drift: Deviation from target schedule
    - Work Time:
    """
    tick_seq: int
    latency_ms: float
    drift_ms: float
    work_time_ms: float

@dataclass(kw_only=True)
class LockEvent(LogEvent):
    """
    Records contention: time spent waiting for a resource.
    """
    lock_name: str
    wait_ms: float
    held_ms: float
    context: str

@dataclass(kw_only=True)
class QueueStatEvent(LogEvent):
    """
    Records buffer occupancy stats.
    
    Metrics:
    - Size vs Capacity: Indicates utilization and backpressure.
    - Dropped: Number of items discarded.
    """
    queue_name: str
    size: int
    capacity: int
    dropped: int

@dataclass(kw_only=True)
class MetricEvent(LogEvent):
    """
    Generic metric event used in subsystems like traffic, energy, water.
    """
    payload: dict[str, Any]