# logger/logger.py

import os
import json
import datetime
import threading

# Global session info
SESSION_ID = None
SESSION_DIR = None
EVENT_LOG_TXT = None
EVENT_LOG_JSONL = None

def start_session(topology_file, topology_summary):
    global SESSION_ID, SESSION_DIR, EVENT_LOG_TXT, EVENT_LOG_JSONL

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    topo_name = os.path.splitext(os.path.basename(topology_file))[0]
    SESSION_ID = f"session_{topo_name}_{timestamp}"

    SESSION_DIR = os.path.join(os.path.dirname(__file__), "logs", SESSION_ID)
    os.makedirs(SESSION_DIR, exist_ok=True)

    # Save session metadata
    meta = {
        "session_id": SESSION_ID,
        "topology_file": topology_file,
        "topology_summary": topology_summary,
        "started_at": datetime.datetime.now().isoformat()
    }
    with open(os.path.join(SESSION_DIR, "session_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Create logs
    EVENT_LOG_TXT = open(os.path.join(SESSION_DIR, "events.txt"), "w")
    EVENT_LOG_JSONL = open(os.path.join(SESSION_DIR, "events.jsonl"), "w")

    log_event("system", f"Session started for {topo_name}", source="logger")

def log_event(event_type, message, source="system", extra_data=None):
    now = datetime.datetime.now().isoformat()
    event = {
        "timestamp": now,
        "type": event_type,
        "message": message,
        "source": source,
        "session": SESSION_ID
    }
    if extra_data:
        event.update(extra_data)

    text_line = f"[{now}] [{event_type.upper()}] [{source}] {message}"
    print(text_line)

    if EVENT_LOG_TXT:
        EVENT_LOG_TXT.write(text_line + "\n")
        EVENT_LOG_TXT.flush()

    if EVENT_LOG_JSONL:
        EVENT_LOG_JSONL.write(json.dumps(event) + "\n")
        EVENT_LOG_JSONL.flush()

def close_logger():
    if EVENT_LOG_TXT:
        EVENT_LOG_TXT.close()
    if EVENT_LOG_JSONL:
        EVENT_LOG_JSONL.close()
