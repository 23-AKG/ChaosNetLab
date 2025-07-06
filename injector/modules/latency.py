import subprocess

def add_latency(interface="eth0", delay_ms=100):
    cmd = f"sudo tc qdisc add dev {interface} root netem delay {delay_ms}ms"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Latency of {delay_ms}ms added to {interface}")
    except subprocess.CalledProcessError:
        print("[!] Error adding latency. Maybe rule already exists?")

def clear_latency(interface="eth0"):
    cmd = f"sudo tc qdisc del dev {interface} root netem"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Latency removed from {interface}")
    except subprocess.CalledProcessError:
        print("[!] No existing latency rule to clear.")
