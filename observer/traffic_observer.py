from logger.logger import log_event

import re

def observe_fault(net, target, fault_type):
    try:
        hosts = net.hosts
        other_hosts = [h for h in hosts if h.name != target]
        target_host = net.get(target)

        for src in other_hosts:
            cmd = f"ping -c 5 {target_host.IP()}"
            output = src.cmd(cmd)

            # Try to extract stats from ping
            loss_match = re.search(r'(\d+)% packet loss', output)
            rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/', output)

            if loss_match:
                packet_loss = int(loss_match.group(1))
            else:
                packet_loss = None

            if rtt_match:
                avg_latency = float(rtt_match.group(2))
            else:
                avg_latency = None

            # Impact analysis
            if packet_loss == 100:
                impact = "critical"
                status = "no connectivity"
            elif packet_loss > 50 or (avg_latency and avg_latency > 200):
                impact = "degraded"
                status = "high loss or latency"
            elif packet_loss is None:
                impact = "unknown"
                status = "could not parse ping"
            else:
                impact = "normal"
                status = "reachable"

            message = (
                f"Ping {src.name} → {target}: "
                f"loss={packet_loss if packet_loss is not None else 'N/A'}%, "
                f"avg latency={avg_latency if avg_latency is not None else 'N/A'}ms "
                f"→ impact={impact} ({status})"
            )

            log_event("observation", message, source="observer")

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
