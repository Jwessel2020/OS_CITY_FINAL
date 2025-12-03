import time
import random
from src.subsystems.base import Subsystem
from src.core.buffer import BoundedBuffer

class EnergySubsystem(Subsystem):
    """
    CONSUMER: Manages Grid and processes EV charging requests.
    
    ----------------------------------------------------------------------------
    OS CONCEPTS DEMONSTRATED:
    
    1. CONSUMER ROLE:
       Energy pulls work items from the buffer. This mimics a worker thread
       handling requests (e.g., web server workers, disk I/O scheduler).
       
    2. BOTTLENECK SIMULATION:
       We intentionally make this consumer slow (`sleep(0.2)` + max 1 item/tick).
       This creates the condition where Consumption Rate < Production Rate,
       which forces the system to buffer items and eventually apply backpressure.
       
    3. BLOCKING GET:
       We call `ev_buffer.get(timeout=...)`. If the buffer is empty, this thread
       will sleep (Blocked) until the Producer puts data in.
    ----------------------------------------------------------------------------
    """
    
    def __init__(self, name, simulation, ev_buffer: BoundedBuffer, interval=0.5):
        super().__init__(name, simulation, interval)
        self.ev_buffer = ev_buffer
        self.base_load_mw = 50.0
        self.ev_load_mw = 0.0

    def execute_tick(self):
        # 1. Check Environment / Scenario Conditions
        # In a real OS, this would be checking for thermal throttling or power states.
        
        # Normal: Fast processing, handle multiple items.
        processing_delay = 0.1
        max_items = 3
        
        if hasattr(self.simulation, 'active_scenario') and self.simulation.active_scenario == "PowerOutage":
            # SCENARIO IMPACT: Drastic slowdown during outage.
            # Simulates brownout conditions where work takes longer and we can handle less.
            processing_delay = 0.6 
            max_items = 1

        # 1. Process Incoming EV Requests (Consumer Logic)
        processed_kwh = 0
        requests_processed = 0
        
        # Simulate being busy/slow (I/O or Compute latency)
        time.sleep(processing_delay)
        
        # Consume up to max_items per tick
        for _ in range(max_items):
            try:
                # Blocking Get: Wait up to 0.05s for work.
                # If buffer is empty, we yield CPU.
                item = self.ev_buffer.get(timeout=0.05)
                if item:
                    processed_kwh += item["kwh"]
                    requests_processed += 1
                else:
                    break # Empty
            except StopIteration:
                break # Buffer closed
        
        # 2. Update Grid State
        self.ev_load_mw = processed_kwh / 1000.0 # Fake conversion
        total_load = self.base_load_mw + self.ev_load_mw
        
        # Simulate Grid Physics (CPU work)
        time.sleep(random.uniform(0.02, 0.08))
        
        # 3. Log Metrics
        self.log_metric({
            "total_load_mw": total_load,
            "ev_load_mw": self.ev_load_mw,
            "requests_processed": requests_processed
        })
