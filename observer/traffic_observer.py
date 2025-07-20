from logger.logger import log_event
import re

def observe_fault(net, target, fault_type):
    try:
        hosts = net.hosts
        target_host = net.get(target)
        target_ip = target_host.IP()
        other_hosts = [h for h in hosts if h.name != target]

        for src in other_hosts:
            cmd = f"ping -c 5 {target_ip}"
            output = src.cmd(cmd)

            # Regex parsing
            loss_match = re.search(r'(\d+)% packet loss', output)
            rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)', output)

            packet_loss = int(loss_match.group(1)) if loss_match else None
            avg_latency = float(rtt_match.group(2)) if rtt_match else None
            jitter = float(rtt_match.group(4)) if rtt_match else None

            # Determine impact
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

            # Log structured observation
            log_event("observation", {
                "source": src.name,
                "destination": target,
                "target_ip": target_ip,
                "loss_percent": packet_loss,
                "avg_latency_ms": avg_latency,
                "jitter_ms": jitter,
                "impact": impact,
                "status": status,
                "fault_type": fault_type
            }, source="observer")

    except Exception as e:
        log_event("observation", f"Error observing fault on {target}: {str(e)}", source="observer")


def _ping_all_to_target(net, target, fault_type):
    for host in net.hosts:
        if host.name != target:
            result = host.cmd(f"ping -c 4 {target}")
            summary = _parse_ping_result(result)
            log_event("observation", f"Ping {host.name} → {target}: {summary}", source="observer")

def _check_connectivity_loss(net, target):
    for host in net.hosts:
        if host.name != target:
            result = host.cmd(f"ping -c 2 {target}")
            if "100% packet loss" in result:
                status = "Target unreachable as expected"
            else:
                status = "Target still reachable — unexpected"
            log_event("observation", f"Down Check {host.name} → {target}: {status}", source="observer")

def _parse_ping_result(output):
    lines = output.splitlines()
    for line in lines:
        if "rtt min/avg/max" in line:
            return line.split('=')[1].strip()
        if "packet loss" in line:
            return line.strip()
    return "No useful ping output"
