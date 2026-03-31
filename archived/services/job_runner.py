"""
Job Runner for Indaba.
Background thread to execute autonomous content production loop.
"""
import time
import threading
from .execution_engine import run_once

class JobRunner:
    def __init__(self, interval=60):
        self.interval = interval
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        
    def start(self):
        with self._lock:
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._run_loop, daemon=True)
                self.thread.start()
                print("[JobRunner] Background execution started.")

    def stop(self):
        with self._lock:
            self.running = False
            print("[JobRunner] Background execution stopped.")

    def _run_loop(self):
        while self.running:
            try:
                print(f"[JobRunner] Executing cycle at {time.strftime('%H:%M:%S')}")
                result = run_once()
                if result.get("status") == "success":
                    print(f"   ✓ Executed: {result['action']['label']}")
                elif result.get("status") == "idle":
                    print(f"   - Idle: {result['message']}")
                else:
                    print(f"   ✗ Error: {result.get('message')}")
            except Exception as e:
                print(f"[JobRunner] Critical error in loop: {e}")
                
            time.sleep(self.interval)

# Singleton instance
runner_instance = JobRunner(interval=30) # 30 seconds for active loop demo
