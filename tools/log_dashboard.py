import json
from collections import Counter
from pathlib import Path
import sys

def load_logs(log_file):
    events = []
    with open(log_file, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return events

def summarize_logs(events):
    injections = [e for e in events if e['type'] == 'injection']
    observations = [e for e in events if e['type'] == 'observation']

    print("\n─────────────── Fault Summary ───────────────")
    for inj in injections:
        print(f"[✓] {inj['message']}")

    print("\n──────────── Observation Summary ─────────────")
    impact_counter = Counter()
    for obs in observations:
        msg = obs.get('message')
        if isinstance(msg, dict):
            src = msg.get("source")
            dst = msg.get("destination")
            loss = msg.get("loss_percent", 'N/A')
            latency = msg.get("avg_latency_ms", 'N/A')
            jitter = msg.get("jitter_ms", 'N/A')
            pdr = msg.get("pdr", 'N/A')
            throughput = msg.get("throughput_mbps", 'N/A')
            impact = msg.get("impact", 'N/A')
            status = msg.get("status", '')

            print(f"{src} → {dst} | loss={loss}%, latency={latency}ms, jitter={jitter}ms, PDR={pdr}%, "
                  f"throughput={throughput} Mbps → impact={impact} ({status})")
            impact_counter[impact] += 1

    print("\n─────────────── Stats ───────────────")
    print(f"Total Faults Injected: {len(injections)}")
    print(f"Total Observations Logged: {len(observations)}")
    for level in ['critical', 'degraded', 'normal', 'unknown']:
        print(f"{level.capitalize()}: {impact_counter[level]}")

if __name__ == "__main__":
    base_dir = Path("logger/logs")
    session_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()], reverse=True)

    if not session_dirs:
        print("[❌] No session folders found.")
        sys.exit(1)

    latest_session = session_dirs[0]
    jsonl_files = sorted(latest_session.glob("*.jsonl"), reverse=True)

    if not jsonl_files:
        print(f"[❌] No '.jsonl' event logs found in {latest_session}")
        sys.exit(1)

    log_file = jsonl_files[0]
    print(f"📁 Using log file: {log_file}")
    events = load_logs(log_file)
    summarize_logs(events)
