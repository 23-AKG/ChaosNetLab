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
import subprocess

# Adding project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from logger.logger import start_session, log_event
from observer.traffic_observer import observe_fault


class CustomTopo(Topo):
    def build(self, topo_config):
        switches = {}
        hosts = {}

        # Add switches if any
        for sw in topo_config.get('switches', []):
            sw_id = sw['id']
            switches[sw_id] = self.addSwitch(sw_id)
            log_event("topology", f"Switch added: {sw_id}", source="topo-builder")

        # Add hosts
        for host in topo_config.get('hosts', []):
            host_id = host['id']
            hosts[host_id] = self.addHost(host_id, ip=host['ip'])
            log_event("topology", f"Host added: {host_id} with IP {host['ip']}", source="topo-builder")

        # Add links
        for link in topo_config.get('links', []):
            src = link['endpoints'][0]
            dst = link['endpoints'][1]
            delay = link.get('delay', '0ms')
            loss = link.get('loss', '0%')
            bw = link.get('bw', None)  # Optional bandwidth field

            params = {
                'delay': delay,
                'loss': float(loss.replace('%', ''))
            }
            if bw:
                params['bw'] = int(bw)

            try:
                self.addLink(src, dst, cls=TCLink, **params)
                log_event("topology", f"Link added: {src} <-> {dst} | delay={delay}, loss={loss}, bw={bw}", source="topo-builder")
            except Exception as e:
                log_event("topology", f"Failed to add link {src} <-> {dst}: {str(e)}", source="topo-builder")


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

                # Handle link-level faults FIRST
                if fault_type in ["linkdown", "linkup"]:
                    try:
                        node1, node2 = target.split('-')
                        action = "down" if fault_type == "linkdown" else "up"
                        net.configLinkStatus(node1.strip(), node2.strip(), action)
                        log_event("injection", f"Link {node1} <-> {node2} set {action.upper()}", source="fault-listener")
                        print(f"[INJECTED] Link {node1} <-> {node2} set {action.upper()}")
                        client.send(f"✅ Link {node1}-{node2} set {action}".encode())
                    except Exception as e:
                        log_event("injection", f"Failed to set link {target} {action}: {str(e)}", source="fault-listener")
                        client.send(f"❌ Failed to update link {target}: {str(e)}".encode())
                    return  # Exit early after link fault is handled

                # Proceed with host-based faults
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
                    result += host_obj.cmd(f"ifconfig {iface} up")
                    # Bring links back up (only once for reset)
                    for link in net.links:
                        n1 = link.intf1.node.name
                        n2 = link.intf2.node.name
                        net.configLinkStatus(n1, n2, "up")

                elif fault_type == "linkdown" or fault_type == "linkup":
                    try:
                        node1, node2 = target.split('-')
                        action = "down" if fault_type == "linkdown" else "up"
                        net.configLinkStatus(node1.strip(), node2.strip(), action)
                        log_event("injection", f"Link {node1} <-> {node2} set {action.upper()}", source="fault-listener")
                        print(f"[INJECTED] Link {node1} <-> {node2} set {action.upper()}")
                        client.send(f"✅ Link {node1}-{node2} set {action}".encode())
                    except Exception as e:
                        log_event("injection", f"Failed to set link {target} {action}: {str(e)}", source="fault-listener")
                        client.send(f"❌ Failed to update link {target}: {str(e)}".encode())
                else:
                    result = f"Unsupported fault type: {fault_type}"

                log_event("injection", f"Injected {fault_type} on {target} (iface={iface}, value={value})", source="fault-listener")
                print(f"[INJECTED] {fault_type} on {target} -> {result.strip()}")
                client.send(f"✅ Injected {fault_type} on {target}".encode())
                observe_fault(net, target, fault_type)
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
    # Build Mininet with OVSController
    from mininet.node import OVSController  # Required for Open vSwitch
    net = Mininet(topo=topo, link=TCLink, controller=OVSController)  # Use OVSController
    net.start()  # Start the network

    # Setup fault listener infrastructure
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('127.0.0.1', 9999))
    stop_event = threading.Event()
    threading.Thread(target=fault_listener, args=(net, server_socket, stop_event), daemon=True).start()

    print("[*] Network started. Running CLI...")
    log_event("system", "Mininet network started", source="testbed")
    CLI(net)

    # Clean shutdown
    stop_event.set()
    server_socket.close()
    net.stop()
    log_event("system", "Mininet network stopped", source="testbed")
    subprocess.run(["mn", "-c"])  # force cleanup


if __name__ == '__main__':
    setLogLevel('info')
    if len(sys.argv) < 2:
        print("Usage: sudo python3 mininet_launcher.py <topology.yaml>")
    else:
        launch_topology(sys.argv[1])
