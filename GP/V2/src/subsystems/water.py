import time
import random
from src.subsystems.base import Subsystem
from src.core.buffer import BoundedBuffer

class WaterSubsystem(Subsystem):
    """
    CONSUMER & PRODUCER: 
    - Consumes energy availability (logical dependency)
    - Produces water supply status (metric)
    - Can be affected by PowerOutage to simulate degraded service.
    
    Demonstrates:
    - Resource dependency chain (Water needs Energy)
    - Performance degradation under resource constraint
    """
    
    def __init__(self, name, simulation, interval=0.5):
        super().__init__(name, simulation, interval)
        self.pumping_capacity = 100.0
        self.reservoir_level = 50.0
        
        # Internal simulated queue of water requests to process
        self.request_queue_depth = 0

    def execute_tick(self):
        # 1. Check Environment / Scenario Conditions
        # In a real OS, this would be checking resource availability (CPU quotas, Memory)
        power_factor = 1.0
        
        # Check if "PowerOutage" scenario is active affecting us
        # (We'll implement a clean way to check this via simulation context later)
        if hasattr(self.simulation, 'active_scenario') and self.simulation.active_scenario == "PowerOutage":
            power_factor = 0.2 # 80% capacity loss due to outage
            
        # 2. Simulate Work (Pumping)
        # Reduced power = Slower pumping = Longer work time per unit of water
        
        # Simulate incoming demand (random fluctuation)
        # Increased demand to make the queue dynamics more visible
        new_requests = random.randint(5, 15)
        self.request_queue_depth += new_requests
        
        # Process requests based on capacity
        # Normal: Process 15 reqs/tick. Outage: Process 3 reqs/tick.
        # This ensures we clear the queue normally, but backlog grows fast during outage.
        capacity_per_tick = int(15 * power_factor)
        
        processed = min(self.request_queue_depth, capacity_per_tick)
        self.request_queue_depth -= processed
        
        # Simulate CPU work proportional to processed items
        # If we have capacity but no requests, work is fast.
        # If we have requests but low capacity (outage), work might take longer due to "retry/struggle" overhead
        # OR we just sleep less because we do less? 
        # Let's model "struggle": Low power means pumps run slower, so moving same water takes longer.
        base_work_ms = 10
        if processed > 0:
            # Time to pump 1 unit = 5ms normally. 
            # With low power, maybe efficient pumps are off, using inefficient backup?
            # Let's keep it simple: Work is proportional to processed volume.
            time.sleep((processed * 0.005) / power_factor) # Slower work if power_factor is low? 
            # Actually, if power is low, we process FEWER items.
            # So let's simulate that the "check/retry" logic for the backlog takes time.
            
        # If backlog is high (due to outage), we spend time managing the queue/backlog
        if self.request_queue_depth > 20:
             time.sleep(0.05) # Overhead of managing backlog
        
        # 3. Update State
        self.reservoir_level += (processed * 0.1) - (random.random() * 0.5)
        self.reservoir_level = max(0, min(100, self.reservoir_level))
        
        # 4. Log Metrics
        self.log_metric({
            "reservoir_level": self.reservoir_level,
            "pending_requests": self.request_queue_depth,
            "pumping_capacity_util": processed / 10.0,
            "power_factor": power_factor
        })

