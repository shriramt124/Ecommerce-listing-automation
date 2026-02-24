"""
AI Telemetry Broadcast Engine
=============================
A global singleton used to stream structured JSON events from the AI Agents
directly to the React Frontend via WebSocket for the Live AI Visualizer.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio

class TelemetryEmitter:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryEmitter, cls).__new__(cls)
            cls._instance.queues = []
        return cls._instance
    
    def subscribe(self) -> asyncio.Queue:
        """Called by the FastAPI WebSocket handler to listen for events."""
        q = asyncio.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.queues:
            self.queues.remove(q)

    def emit(self, agent: str, action: str, data: Dict[str, Any] = None):
        """Broadcast an event to all connected UI clients."""
        payload = {
            "type": "agent_telemetry",
            "agent": agent,
            "action": action,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Inter-Process Communication (IPC) for UI Subprocess
        if os.environ.get("ADKRUX_TELEMETRY_IPC") == "1":
            try:
                # Use a specific prefix so job_manager.py can catch it
                print(f"__TELEMETRY__:{json.dumps(payload)}", flush=True)
            except Exception:
                pass

        if not self.queues:
            return  # Nobody listening natively, skip local enqeue


        
        msg = json.dumps(payload)
        for q in self.queues:
            try:
                q.put_nowait(msg)
            except Exception:
                pass


# Global singleton instance
emitter = TelemetryEmitter()

def emit_telemetry(agent: str, action: str, data: Dict[str, Any] = None):
    """Convenience function for agents to fire events."""
    emitter.emit(agent, action, data)
