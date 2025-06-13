#!/usr/bin/env python
import asyncio
import os
import sys
import platform
import threading
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from main import background_worker_loop

# Apply asyncio policy patch for Windows if applicable
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Track worker status
worker_status = {
    "start_time": time.time(),
    "last_task_time": None,
    "is_healthy": True,
    "error_count": 0
}

# Simple HTTP server for health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        # Update status before sending
        current_status = {
            "status": "healthy" if worker_status["is_healthy"] else "unhealthy",
            "uptime_seconds": int(time.time() - worker_status["start_time"]),
            "last_task_time": worker_status["last_task_time"],
            "error_count": worker_status["error_count"]
        }
        
        self.wfile.write(json.dumps(current_status).encode())
        
    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        return

def start_health_check_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), HealthCheckHandler)
    print(f"Starting health check server on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    print("Starting ThinkStash AI Worker...")
    
    # Start health check server in a separate thread
    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()
    print("Health check server running in background")
    
    try:
        # Run the background worker loop
        asyncio.run(background_worker_loop())
    except KeyboardInterrupt:
        print("Worker stopped by user.")
        worker_status["is_healthy"] = False
    except Exception as e:
        print(f"Worker failed with error: {e}")
        worker_status["is_healthy"] = False
        worker_status["error_count"] += 1
        sys.exit(1) 