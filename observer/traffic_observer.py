from logger.logger import log_event
import re
import time
import subprocess

def observe_fault(net, target, fault_type):
    try:
        hosts = net.hosts
        target_host = net.get(target)
        target_ip = target_host.IP()
        other_hosts = [h for h in hosts if h.name != target]

        for src in other_hosts:
            # Step 1: Ping
            cmd = f"ping -c 5 {target_ip}"
            output = src.cmd(cmd)

            # Extract loss, latency, jitter
            loss_match = re.search(r'(\d+)% packet loss', output)
            rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)', output)
            tx_match = re.search(r'(\d+) packets transmitted', output)
            rx_match = re.search(r'(\d+) received', output)

            packet_loss = int(loss_match.group(1)) if loss_match else None
            avg_latency = float(rtt_match.group(2)) if rtt_match else None
            jitter = float(rtt_match.group(4)) if rtt_match else None

            # Step 2: PDR
            if tx_match and rx_match:
                tx = int(tx_match.group(1))
                rx = int(rx_match.group(1))
                pdr = round((rx / tx) * 100, 2) if tx > 0 else None
            else:
                pdr = None

            # Step 3: Throughput using iperf
            throughput = None
            try:
                # Start iperf server on target
                target_proc = target_host.popen("iperf -s -u -p 5001", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)

                # Run client from src to target
                iperf_output = src.cmd(f"iperf -u -c {target_ip} -p 5001 -t 5")
                match = re.search(r'([\d\.]+)\s+Mbits/sec', iperf_output)
                if match:
                    throughput = float(match.group(1))
                target_proc.terminate()
            except Exception as e:
                pass  # skip if iperf fails

            # Step 4: Impact analysis
            if packet_loss == 100:
                impact = "critical"
                status = "no connectivity"
            elif packet_loss is None:
                impact = "unknown"
                status = "unparsable ping output"
            elif packet_loss > 50 or (avg_latency and avg_latency > 200):
                impact = "degraded"
                status = "high loss or latency"
            else:
                impact = "normal"
                status = "reachable"

            # Log everything
            log_event("observation", {
                "source": src.name,
                "destination": target,
                "target_ip": target_ip,
                "loss_percent": packet_loss,
                "avg_latency_ms": avg_latency,
                "jitter_ms": jitter,
                "pdr": pdr,
                "throughput_mbps": throughput,
                "impact": impact,
                "status": status,
                "fault_type": fault_type
            }, source="observer")

    except Exception as e:
        log_event("observation", f"Error observing fault on {target}: {str(e)}", source="observer")
