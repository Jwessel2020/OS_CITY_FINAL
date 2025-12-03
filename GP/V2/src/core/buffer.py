import threading
import time
import uuid
from typing import TypeVar, Generic, Optional
from collections import deque

T = TypeVar('T')

def os_trace(msg):
    #method to print low level OS events for demonstration and analysis.
    print(f"[OS-TRACE] {time.time():.4f} | {threading.current_thread().name:<15} | {msg}", flush=True)

class BoundedBuffer(Generic[T]):
    """
    A thread-safe bounded buffer implementing the Producer-Consumer pattern manually
    using threading.Lock and threading.Condition.
    
    OS CONCEPTS DEMONSTRATED:
    
    1. MUTUAL EXCLUSION:
       We use self._lock = threading.Lock() to be sure only one thread can
       access or modify the buffer at one time. 
       
    2. CONDITION VARIABLES:
       We use self._not_full and self._not_empty condition variables to signal
       state changes.
       - `wait()`: Atomically releases the lock and puts the thread to sleep until signaled.
       - `notify()`: Wakes up a sleeping thread waiting on this condition.

       
    3. BOUNDED BUFFER (Backpressure):
       The buffer has a fixed capacity. Producers must block/wait if the buffer
       is full.
       
    4. BLOCKING I/O & TIMEOUTS:
       Operations put() and get() can block. We support timeout to allow
       threads to wake up to check for shutdown signals or handle errors,
       preventing permanent deadlocks if a partnered thread crashes.
    """
    
    def __init__(self, capacity: int, name: str = "Buffer"):
        self.capacity = capacity
        self.name = name
        self._buffer: deque[T] = deque()
        self._lock = threading.Lock()
        
        # Condition variables for coordination
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)
        
        self._closed = False
        
        # Instrumentation stats for observability
        self.stats = {
            "puts": 0,
            "gets": 0,
            "waits_for_space": 0, # Metric for Producer blocking (Contention)
            "waits_for_item": 0,  # Metric for Consumer blocking (Starvation)
            "drop_count": 0
        }
        
        # For sequence tracking
        self.op_counter = 0

    def put(self, item: T, timeout: Optional[float] = None) -> bool:

        #Add an item to the buffer. Blocks if full until space is available or timeout.
        op_id = str(uuid.uuid4())[:8]
        os_trace(f"[Op:{op_id}] buffer.put() called. Acquiring Lock for {self.name}...")
        start_time = time.perf_counter()
        
        with self._lock:
            self.op_counter += 1
            seq = self.op_counter
            os_trace(f"[Op:{op_id}] Lock Acquired (Seq:{seq}). Checking capacity ({len(self._buffer)}/{self.capacity}).")
            
            if self._closed:
                raise ValueError(f"Buffer {self.name} is closed")
                
            while len(self._buffer) >= self.capacity:
                os_trace(f"[Op:{op_id}] Buffer FULL. Sleeping on Condition (not_full). Waiters approx: ?")
                self.stats["waits_for_space"] += 1
                
                # Wait releases the lock and blocks until notified or timeout
                wait_start = time.perf_counter()
                success = self._not_full.wait(timeout=timeout)
                wait_time = (time.perf_counter() - wait_start) * 1000
                
                os_trace(f"[Op:{op_id}] Woke up from wait. Success={success}. Waited {wait_time:.2f}ms. Re-checking state.")
                
                if self._closed:
                    raise ValueError(f"Buffer {self.name} is closed")
                    
                if not success:
                    os_trace(f"[Op:{op_id}] Timed out waiting for space.")
                    return False # Timed out
            
            self._buffer.append(item)
            self.stats["puts"] += 1
            
            # Signal consumers that an item is available
            os_trace(f"[Op:{op_id}] Item added. New Size: {len(self._buffer)}. Signalling Condition (not_empty).")
            self._not_empty.notify()
            os_trace(f"[Op:{op_id}] Releasing Lock.")
            return True

    def get(self, timeout: Optional[float] = None) -> Optional[T]:

       # Remove and return an item. Blocks if empty until item available or timeout.

        op_id = str(uuid.uuid4())[:8]
        os_trace(f"[Op:{op_id}] buffer.get() called. Acquiring Lock for {self.name}...")
        
        with self._lock:
            self.op_counter += 1
            seq = self.op_counter
            os_trace(f"[Op:{op_id}] Lock Acquired (Seq:{seq}). Checking emptiness (Size: {len(self._buffer)}).")
            
            while not self._buffer:
                if self._closed:
                    os_trace(f"[Op:{op_id}] Buffer closed & empty. StopIteration.")
                    raise StopIteration("Buffer closed and empty")
                
                os_trace(f"[Op:{op_id}] Buffer EMPTY. Sleeping on Condition (not_empty).")
                self.stats["waits_for_item"] += 1
                
                wait_start = time.perf_counter()
                success = self._not_empty.wait(timeout=timeout)
                wait_time = (time.perf_counter() - wait_start) * 1000
                
                os_trace(f"[Op:{op_id}] Woke up from wait. Success={success}. Waited {wait_time:.2f}ms.")
                
                if not success:
                    os_trace(f"[Op:{op_id}] Timed out waiting for item.")
                    return None # Timed out
            
            item = self._buffer.popleft()
            self.stats["gets"] += 1
            
            # Signal producers that space is available
            os_trace(f"[Op:{op_id}] Item removed. New Size: {len(self._buffer)}. Signalling Condition (not_full).")
            self._not_full.notify()
            os_trace(f"[Op:{op_id}] Releasing Lock.")
            return item

    def try_put(self, item: T) -> bool:

       # Non-blocking put. Returns True if added, False if full.

        with self._lock:
            if self._closed:
                return False
            
            if len(self._buffer) >= self.capacity:
                self.stats["drop_count"] += 1
                return False
            
            self._buffer.append(item)
            self.stats["puts"] += 1
            self._not_empty.notify()
            return True

    def close(self) -> None:
        """
        Close the buffer. No more puts allowed. 
        """
        os_trace(f"Closing buffer {self.name}. Waking all threads.")
        with self._lock:
            self._closed = True
            # Wake up everyone so they check the closed flag
            self._not_empty.notify_all()
            self._not_full.notify_all()

    def qsize(self) -> int:
        """Return current number of items (Thread-safe)."""
        with self._lock:
            return len(self._buffer)
            
    def is_full(self) -> bool:
        """Check if buffer is full (Thread-safe)."""
        with self._lock:
            return len(self._buffer) >= self.capacity
