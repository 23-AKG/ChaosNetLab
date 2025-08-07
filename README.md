# ChaosNetLab – SDN Fault-Injection Framework

ChaosNetLab is a lightweight framework for building and testing virtual network topologies in Mininet and injecting faults to observe their impact. It is designed for researchers, students and network engineers who want to explore how link failures, packet loss, delay or firewall rules affect connectivity and performance in Software-Defined Networking (SDN) environments.

## Features

* **YAML-based topology definition**: describe hosts, switches, routers, firewalls and links with optional bandwidth, delay and loss parameters.
* **Automated network set-up**: assign IP addresses, enable IP forwarding, configure static routes, apply firewall rules and set default routes automatically.
* **Interactive CLI**: launch topologies and inject faults (e.g., packet loss, delay, interface down, link down/up, netem reset) using a simple command-line interface built with `click`.
* **Fault injection server**: a background listener accepts JSON-formatted fault commands over a localhost TCP socket, applies them in Mininet and reports success or failure.
* **Traffic observation**: after each fault injection, the framework pings the affected host from all other hosts, measures packet loss, average latency, jitter, packet-delivery ratio and throughput (via `iperf`), and classifies the impact as critical, degraded, normal or unknown.
* **Logging and dashboards**: all events are written as human-readable text and structured JSONL files. A helper script summarises faults and their impacts.
* **Connectivity testing**: an optional tester script attaches to a running topology and performs basic connectivity and firewall enforcement checks.

## Prerequisites

This framework targets a Linux environment with root privileges (required by Mininet and network tools). You will need:

* Python 3.7 or newer
* Mininet installed and working  ([Mininet](http://mininet.org/))
* `iperf` for throughput measurement
* `tc` and `iproute2` for traffic shaping (netem)
* `iptables` for firewall rules

Install optional Python dependencies via pip:

```bash
pip install click PyYAML
```

## Getting Started

1. Clone this repository and change into its directory.

2. Choose or create a topology under `topology/`. Three sample files are provided:

   * `sample_topology.yaml` – two hosts connected to a single switch.
   * `complex_topology.yaml` – multiple hosts and switches with delay/loss parameters.
   * `complex_topology2.yaml` – hosts connected via routers and a firewall.

A topology file describes:

```yaml
hosts:
  - id: h1
    ip: 10.0.0.1/24

routers:
  - id: r1
    interfaces:
      - name: r1-eth0
        ip: 10.0.0.254/24
    routes:
      - dest: 10.0.1.0/24
        via: 192.168.1.2

firewalls:
  - id: fw1
    interfaces:
      - name: fw1-eth0
        ip: 10.0.1.253/24
    rules:
      - action: DROP
        src: 10.0.0.2

switches:
  - id: s1

links:
  - endpoints: [h1, s1]
    delay: 10ms
    loss: 0.1%
```

3. Launch the network (requires root):

```bash
sudo python3 cli/main.py launch --topo complex_topology2.yaml
```

The launcher will parse the YAML, validate the configuration, create the Mininet network, configure IP addresses and routes, start a fault-listener thread and drop you into the Mininet CLI.

4. Inject faults from a new terminal:

```bash
# Simulate 30% packet loss on host h1
python3 cli/main.py inject --target h1 --type loss --value 30%

# Add 100 ms delay to h2's interface
python3 cli/main.py inject --target h2 --type delay --value 100ms

# Bring the link between s1 and s2 down
python3 cli/main.py inject --target s1-s2 --type linkdown
```

After each injection, the observer will measure connectivity and log metrics such as loss, latency, jitter and throughput.

5. View logs and summaries:

```bash
python3 tools/log_dashboard.py
```

This prints a fault summary and impact statistics from the latest session.

6. Run connectivity tests (optional):

```bash
sudo python3 tools/topology_tester.py
```

This script pings between all hosts and checks that firewall rules block or allow traffic appropriately.

## Development Notes

* The fault-listener currently exits after handling a link-level fault due to a `return` statement; replacing it with `continue` keeps the listener alive.
* Duplicate configuration loops for routers and firewalls can be consolidated for clarity.
* The project binds the fault-listener to `127.0.0.1` without authentication. If you run this on a shared machine, consider adding an authentication mechanism.

## Contributors
Akarsh Kumar Gowda
Pranav P Kulkarni
Prem SP

---

Contributions are welcome! Feel free to open issues or pull requests to improve validation, add support for new fault types, or extend logging and dashboard capabilities.
