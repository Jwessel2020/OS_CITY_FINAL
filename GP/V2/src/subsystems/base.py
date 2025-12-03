import threading
import time
import logging
from typing import Optional

from src.core.metrics import TickEvent, MetricEvent

logger = logging.getLogger("Subsystem")

class Subsystem(threading.Thread):
    """
    Base class for all city subsystems.
    
    OS CONCEPTS DEMONSTRATED:
    
    1. PROCESS/THREAD MODEL:
       Each subsystem runs as an independent OS thread. This demonstrates
       Concurrent Execution—multiple tasks making progress simultaneously
       on the host OS scheduler.
       
    2. SCHEDULING & REAL TIME CONSTRAINTS:
       We implement a Tick Loop acting as a mini scheduler).
       - Target Interval: 0.5s (e.g., 2 Hz).
       - Drift Compensation
         
    3. INSTRUMENTATION :
       We measure latency_ms vs work_time_ms
       for every single tick. This allows us to detect:
       - CPU Saturation
       - Blocking
    """
    
    def __init__(self, name: str, simulation, interval: float = 1.0):
        super().__init__(name=name, daemon=True)
        self.name = name
        self.simulation = simulation
        self.interval = interval # Target tick duration seconds
        self.last_tick_ts = time.time()
        self.tick_count = 0
        
    def run(self):
        logger.info(f"[{self.name}] Thread Started (TID: {threading.get_native_id()})")
        
        next_tick_time = time.perf_counter()
        
        while self.simulation.running.is_set():
            loop_start = time.perf_counter()
            
            # 1. Do Work
            self.execute_tick()
            self.last_tick_ts = time.time()
            self.tick_count += 1
            
            # 2. Measure Timing
            work_end = time.perf_counter()
            work_duration = (work_end - loop_start) * 1000.0 # ms
            
            # 3. Schedule Next Tick 
            next_tick_time += self.interval
            sleep_duration = next_tick_time - time.perf_counter()
            
            # Log Tick Metrics 
            latency = (time.perf_counter() - loop_start) * 1000.0
            drift = (time.perf_counter() - next_tick_time) * 1000.0
            
            self.simulation.logger.log(TickEvent(
                run_id=self.simulation.logger.run_id,
                subsystem=self.name,
                tick_seq=self.tick_count,
                latency_ms=latency,
                drift_ms=drift,
                work_time_ms=work_duration
            ))
            
            # Voluntary Yield / Sleep
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            else:
                # Yield minimally to allow other threads to run
                time.sleep(0.01)

    def execute_tick(self):
        """Override this method to perform subsystem logic."""
        pass

    def log_metric(self, payload: dict):
        """Helper to log custom metrics."""
        self.simulation.logger.log(MetricEvent(
            run_id=self.simulation.logger.run_id,
            subsystem=self.name,
            payload=payload
        ))
