import yaml
import socket
import threading
import json
import os
import sys
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSController

# Adding project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from logger.logger import start_session, log_event


class CustomTopo(Topo):
    def build(self, topo_config):
        switches = {}
        hosts = {}

        for sw in topo_config.get('switches', []):
            sw_id = sw['id']
            switches[sw_id] = self.addSwitch(sw_id)
            log_event("topology", f"Switch added: {sw_id}", source="topo-builder")

        for host in topo_config.get('hosts', []):
            host_id = host['id']
            hosts[host_id] = self.addHost(host_id, ip=host['ip'])
            log_event("topology", f"Host added: {host_id} with IP {host['ip']}", source="topo-builder")

        for link in topo_config.get('links', []):
            src, dst = link['endpoints']
            delay = link.get('delay', '0ms')
            loss = link.get('loss', '0')
            params = {
                'delay': delay,
                'loss': float(loss.replace('%', ''))
            }
            self.addLink(src, dst, cls=TCLink, **params)
            log_event("topology", f"Link added: {src} <-> {dst} | delay={delay}, loss={loss}", source="topo-builder")


def fault_listener(net, server_socket, stop_event):
    server_socket.listen(5)
    print(f"[CTRL] Listening for fault commands on {server_socket.getsockname()}...")

    while not stop_event.is_set():
        try:
            server_socket.settimeout(1.0)  # Check for shutdown every second
            client, addr = server_socket.accept()
        except socket.timeout:
            continue
        except OSError:
            break  # Socket closed externally

        with client:
            try:
                data = client.recv(1024).decode('utf-8')
                cmd = json.loads(data)
                target = cmd.get("target")
                fault_type = cmd.get("type")
                value = cmd.get("value", "")
                iface = f"{target}-eth0"
                host_obj = net.get(target)

                if fault_type == "loss":
                    result = host_obj.cmd(f"tc qdisc add dev {iface} root netem loss {value}")
                    if "Exclusivity flag" in result or "File exists" in result:
                        result = host_obj.cmd(f"tc qdisc change dev {iface} root netem loss {value}")
                elif fault_type == "delay":
                    result = host_obj.cmd(f"tc qdisc add dev {iface} root netem delay {value}")
                    if "Exclusivity flag" in result or "File exists" in result:
                        result = host_obj.cmd(f"tc qdisc change dev {iface} root netem delay {value}")
                elif fault_type == "down":
                    result = host_obj.cmd(f"ifconfig {iface} down")
                elif fault_type == "reset":
                    result = host_obj.cmd(f"tc qdisc del dev {iface} root")
                else:
                    result = f"Unsupported fault type: {fault_type}"

                log_event("injection", f"Injected {fault_type} on {target} (iface={iface}, value={value})", source="fault-listener")
                print(f"[INJECTED] {fault_type} on {target} -> {result.strip()}")
                client.send(f"✅ Injected {fault_type} on {target}".encode())
            except Exception as e:
                print(f"[ERROR] {e}")
                client.send(f"❌ Failed: {str(e)}".encode())


def launch_topology(yaml_file):
    with open(yaml_file, 'r') as f:
        topo_config = yaml.safe_load(f)

    topology_summary = {
        "hosts": [host['id'] for host in topo_config.get('hosts', [])],
        "switches": [sw['id'] for sw in topo_config.get('switches', [])],
        "links": len(topo_config.get('links', []))
    }

    start_session(yaml_file, topology_summary)

    topo = CustomTopo(topo_config)
    net = Mininet(topo=topo, link=TCLink, controller=OVSController)
    net.addController('c0')

    net.start()
    log_event("system", "Mininet network started", source="testbed")
    print("[*] Network started. Running CLI...")

    # Prepare socket and thread
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.0.1', 9999))
    stop_event = threading.Event()
    listener_thread = threading.Thread(target=fault_listener, args=(net, server_socket, stop_event), daemon=True)
    listener_thread.start()

    try:
        CLI(net)
    finally:
        log_event("system", "Mininet network stopped", source="testbed")
        print("[*] Cleaning up...")
        stop_event.set()
        server_socket.close()
        listener_thread.join(timeout=2)
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    if len(sys.argv) < 2:
        print("Usage: sudo python3 mininet_launcher.py <topology.yaml>")
    else:
        launch_topology(sys.argv[1])
