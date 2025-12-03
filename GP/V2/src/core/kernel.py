import threading
import time
import logging
from typing import Optional

from src.data.database import SqlLogger
from src.core.buffer import BoundedBuffer
from src.core.metrics import MetricEvent
from src.core.scenarios import ScenarioManager


logger = logging.getLogger("CitySimulation")

class CitySimulation:
    """
    The Micro-Kernel that orchestrates the OS simulation.
    
    OS CONCEPTS DEMONSTRATED:
    
    1. KERNEL:
       This class acts as the OS Kernel. It is responsible for:
       - Bootstrapping the system (Initializing hardware/drivers -> Subsystems).
       - Process Management (Starting/Stopping threads).
       - IPC Setup (Creating shared buffers for communication).
       
    2. WATCHDOG:
       Runs a dedicated daemon thread `_watchdog_loop` to monitor system stability.
       - Deadlock Detection: Checks if any subsystem hasn't "ticked" recently.
       - Resource Starvation: Checks if critical buffers are permanently full or empty.
       
    3. INTER-PROCESS COMMUNICATION:
       Wires together independent subsystems (Traffic, Energy) using a shared
       BoundedBuffer (ev_buffer).
    """
    
    def __init__(self):
        self.running = threading.Event()
        self.logger = SqlLogger()
        
        # IPC: Bounded Buffer between Traffic (Prod) and Energy (Cons)
        # Represents EV charging demand flowing from cars to grid.
        # Capacity=10 means if Energy is slow, Traffic can only buffer 10 requests
        self.ev_buffer = BoundedBuffer(capacity=10, name="EV_Charging_Queue")
        
        self.subsystems = []
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="Watchdog", daemon=True)
        self.scenario_manager = ScenarioManager(self)
        self.active_scenario = None # Shared state read by subsystems

    def bootstrap(self):
        """
        Initialize subsystems and wiring 
        Instantiates the worker threads and gives them references to shared resources
        """
        # Only start logger if not already started
        if not self.logger._running:
             self.logger.start()
        
        # We need to import here to avoid circular imports - that was an early bug
        from src.subsystems.traffic import TrafficSubsystem
        from src.subsystems.energy import EnergySubsystem
        from src.subsystems.water import WaterSubsystem
        
        # Initialize Subsystems
        # Traffic produces EV requests -> ev_buffer
        traffic = TrafficSubsystem(
            name="Traffic", 
            simulation=self, 
            ev_buffer=self.ev_buffer,
            interval=0.5
        )
        
        # Energy consumes EV requests <- ev_buffer
        energy = EnergySubsystem(
            name="Energy", 
            simulation=self, 
            ev_buffer=self.ev_buffer,
            interval=0.5
        )
        
        # Water: Self-contained consumer/producer logic
        water = WaterSubsystem(
            name="Water",
            simulation=self,
            interval=0.5
        )
        
        self.subsystems = [traffic, energy, water]
        logger.info("Simulation Bootstrapped. Subsystems: %s", [s.name for s in self.subsystems])

    def start(self):
        """Start all threads (Process Scheduling)."""
        if self.running.is_set():
            return
            
        self.running.set()
        
        for s in self.subsystems:
            s.start()
            
        self._watchdog_thread.start()
        self.scenario_manager.start()
        logger.info("Simulation Started.")

    def stop(self):
        """ shutdown signal (System Halt)."""
        logger.info("Stopping Simulation...")
        self.running.clear()
        self.scenario_manager.stop()
        
        # Signal buffer close to unblock any waiting threads, avoids zombies
        self.ev_buffer.close()
        
        for s in self.subsystems:
            s.join(timeout=1.0)
            
        self.logger.stop()
        logger.info("Simulation Stopped.")

    def toggle_scenario(self, name: str):
        """
        Manually trigger a scenario.
        Gives to the Scenario Manager.
        """
        if self.scenario_manager:
            self.scenario_manager.toggle_scenario(name)

    def _watchdog_loop(self):
        """
        Monitor system health.
        Detects:
        1. Deadlocks
        2. Starvation (Buffer full/empty for too long)
        """
        while self.running.is_set():
            time.sleep(2.0) # Check every 2 seconds
            
            now = time.time()
            
            # 1. Check Subsystem dead or not
            for s in self.subsystems:
                time_since_tick = now - s.last_tick_ts
                if time_since_tick > 5.0:
                    logger.warning(f"WATCHDOG: {s.name} stalled! No tick for {time_since_tick:.1f}s")
                    self.logger.log(MetricEvent(
                        run_id=self.logger.run_id,
                        subsystem="Kernel",
                        payload={"event": "stall_detected", "target": s.name, "duration": time_since_tick}
                    ))

            # 2.Check Buffer state 
            q_size = self.ev_buffer.qsize()
            if q_size == self.ev_buffer.capacity:
                logger.warning(f"WATCHDOG: {self.ev_buffer.name} is FULL ({q_size}). Potential backpressure/deadlock.")
            elif q_size == 0:
                
                pass
            

            from src.core.metrics import QueueStatEvent
            self.logger.log(QueueStatEvent(
                run_id=self.logger.run_id,
                subsystem="Kernel",
                queue_name=self.ev_buffer.name,
                size=q_size,
                capacity=self.ev_buffer.capacity,
                dropped=self.ev_buffer.stats["drop_count"]
            ))
