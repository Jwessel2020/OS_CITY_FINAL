import threading
import time
import logging
from src.core.metrics import MetricEvent

logger = logging.getLogger("ScenarioManager")

class ScenarioManager(threading.Thread):
    """
   controls simulation scenarios
    
    OS CONCEPTS DEMONSTRATED:
    
    1. DYNAMIC WORKLOAD MANAGEMENT:
       Operating Systems must handle varying workloads. This class simulates changing
       conditions to test the responsiveness and stability.

    """
    
    def __init__(self, simulation):
        super().__init__(name="ScenarioManager", daemon=True)
        self.simulation = simulation
        self.active_scenario = None
        self._stop_event = threading.Event()

    def run(self):
        logger.info("ScenarioManager Started (Manual Mode).")
        
        # In manual mode, we just wait until stopped.
        # Scenarios are triggered on the dashboard button calling toggle_scenario()
        self._stop_event.wait()
            
    def stop(self):
        self._stop_event.set()

    def toggle_scenario(self, name: str):
        """Manually toggle a scenario on/off."""
        if self.active_scenario == name:
            self._set_scenario(None)
        else:
            self._set_scenario(name)

    def _set_scenario(self, name: str | None):
        old = self.active_scenario
        self.active_scenario = name
        self.simulation.active_scenario = name # Expose to subsystems with shared state
        
        logger.info(f"SCENARIO CHANGE: {old} -> {name}")
        
        # Log event to SQL
        self.simulation.logger.log(MetricEvent(
            run_id=self.simulation.logger.run_id,
            subsystem="ScenarioManager",
            payload={
                "event": "scenario_change", 
                "previous": old, 
                "current": name,
                "ts": time.time()
            }
        ))
