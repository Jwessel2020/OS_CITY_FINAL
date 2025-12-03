import time
import random
from src.subsystems.base import Subsystem
from src.core.buffer import BoundedBuffer

class TrafficSubsystem(Subsystem):
    """
    PRODUCER: Simulates traffic and generates EV charging requests.
    

    OS CONCEPTS DEMONSTRATED:
    
    1. PRODUCER ROLE:
       Traffic generates work items (EVChargingRequest) and places it into
       a shared buffer.
    2. BACKPRESSURE:
       We use BLOCKING PUT into the ev_buffer. 
       - If the Consumer (Energy) is slow and the buffer fills up (Size=10),
         this thread will SLEEP (blocked state) inside put().
       - This demonstrates how flow control propagates upstream:
         Slow Consumer -> Full Buffer -> Blocked Producer.
    """
    
    def __init__(self, name, simulation, ev_buffer: BoundedBuffer, interval=0.5):
        super().__init__(name, simulation, interval)
        self.ev_buffer = ev_buffer
        self.cars_on_road = 100

    def execute_tick(self):
        # 1  Simulate Traffic Logic
        # Random change traffic density
        change = random.randint(-5, 5)
        self.cars_on_road = max(0, min(500, self.cars_on_road + change))
        
        # Simulate calculation time
        time.sleep(random.uniform(0.01, 0.05))
        
        # 2. Produce EV Charging Requests 
        #We purposely produce 2-4 items per tick.
        # Since Energy only consumes 1 tick, this ensures the buffer fills up,
        # triggering the backpressure demonstration.
        num_requests = random.randint(2, 4)
        
        for _ in range(num_requests):
            req_id = f"EV-{self.tick_count}-{random.randint(0,99)}"
            request = {"id": req_id, "kwh": random.randint(20, 80), "ts": time.time()}
            
            # BLOCKING PUT: Waits for space in buffer
            # timeout=  0.2 prevents infinite deadlocks during debugging, 
            # but effectively blocks for a significant time of tick.
            try:
                success = self.ev_buffer.put(request, timeout=0.2)
                if not success:
                    # If we time out, it means the system is overloaded.
                    # We log a Drop event (Packet Loss).
                    self.log_metric({"event": "ev_req_dropped", "reason": "timeout_full"})
            except ValueError:
                pass # Buffer closed 
        
        # 3. Log Status
        self.log_metric({
            "cars": self.cars_on_road, 
            "congestion": self.cars_on_road / 500.0,
            "generated_requests": num_requests
        })
