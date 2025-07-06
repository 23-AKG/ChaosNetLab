import subprocess

def add_packet_loss(interface="eth0", loss_percent=10):
    cmd = f"sudo tc qdisc add dev {interface} root netem loss {loss_percent}%"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Packet loss of {loss_percent}% added to {interface}")
    except subprocess.CalledProcessError:
        print("[!] Failed to add packet loss. Rule might already exist.")

def clear_packet_loss(interface="eth0"):
    cmd = f"sudo tc qdisc del dev {interface} root netem"
    try:
        subprocess.run(cmd.split(), check=True)
        print(f"[✓] Packet loss cleared from {interface}")
    except subprocess.CalledProcessError:
        print("[!] No packet loss rule to clear.")
