import subprocess
import time

def bring_down(interface="eth0"):
    cmd = f"sudo ip link set {interface} down"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Interface {interface} is now down")
    except subprocess.CalledProcessError:
        print(f"[!] Failed to bring down interface {interface}")

def bring_up(interface="eth0"):
    cmd = f"sudo ip link set {interface} up"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Interface {interface} is back up")
    except subprocess.CalledProcessError:
        print(f"[!] Failed to bring up interface {interface}")

def restart_interface(interface="eth0", downtime=5):
    bring_down(interface)
    print(f"[*] Waiting {downtime} seconds...")
    time.sleep(downtime)
    bring_up(interface)
