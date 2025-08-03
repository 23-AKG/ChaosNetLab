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
import ipaddress
# Adding project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from logger.logger import start_session, log_event
from observer.traffic_observer import observe_fault


class CustomTopo(Topo):
    def build(self, topo_config):
        switches = {}
        hosts = {}
        routers = {}
        firewalls = {}

        # Add switches
        for sw in topo_config.get('switches', []):
            sw_id = sw['id']
            switches[sw_id] = self.addSwitch(sw_id)
            log_event("topology", f"Switch added: {sw_id}", source="topo-builder")

        # Add hosts
        for host in topo_config.get('hosts', []):
            host_id = host['id']
            hosts[host_id] = self.addHost(host_id, ip=host['ip'])
            log_event("topology", f"Host added: {host_id} with IP {host['ip']}", source="topo-builder")

        # Add routers (Linux hosts with forwarding + static routes)
        for router in topo_config.get('routers', []):
            r_id = router['id']
            routers[r_id] = self.addHost(r_id)
            log_event("topology", f"Router added: {r_id}", source="topo-builder")

        # Add firewalls (Linux hosts with iptables)
        for fw in topo_config.get('firewalls', []):
            fw_id = fw['id']
            firewalls[fw_id] = self.addHost(fw_id)
            log_event("topology", f"Firewall added: {fw_id}", source="topo-builder")
        # Add links
        for link in topo_config.get('links', []):
            src, dst = link['endpoints']
            delay = link.get('delay', '0ms')
            loss = link.get('loss', '0%')
            bw = link.get('bw', None)

            params = {'delay': delay, 'loss': float(loss.replace('%', ''))}
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

    

    def validate_topology(topo_config):
        errors = []
        device_ids = set()

        # Collect all devices
        for h in topo_config.get('hosts', []):
            device_ids.add(h['id'])
        for s in topo_config.get('switches', []):
            device_ids.add(s['id'])
        for r in topo_config.get('routers', []):
            device_ids.add(r['id'])
        for f in topo_config.get('firewalls', []):
            device_ids.add(f['id'])

        # Validate Routers
        for r in topo_config.get('routers', []):
            if not r.get('interfaces'):
                msg = f"Router {r['id']} has no interfaces defined."
                errors.append(msg)
                log_event("validation", msg, source="validator")
            for iface in r.get('interfaces', []):
                if not any(r['id'] in link['endpoints'] for link in topo_config.get('links', [])):
                    msg = f"Interface {iface['name']} of Router {r['id']} is not connected in links."
                    errors.append(msg)
                    log_event("validation", msg, source="validator")
            for route in r.get('routes', []):
                try:
                    ipaddress.ip_network(route['dest'])
                    ipaddress.ip_address(route['via'])
                except ValueError:
                    msg = f"Router {r['id']} has invalid route format: {route}"
                    errors.append(msg)
                    log_event("validation", msg, source="validator")

        # Validate Firewalls
        for f in topo_config.get('firewalls', []):
            if len(f.get('interfaces', [])) < 2:
                msg = f"Firewall {f['id']} must have at least 2 interfaces."
                errors.append(msg)
                log_event("validation", msg, source="validator")
            for iface in f.get('interfaces', []):
                if not any(f['id'] in link['endpoints'] for link in topo_config.get('links', [])):
                    msg = f"Interface {iface['name']} of Firewall {f['id']} is not connected in links."
                    errors.append(msg)
                    log_event("validation", msg, source="validator")
            for rule in f.get('rules', []):
                try:
                    ipaddress.ip_address(rule['src'])
                except ValueError:
                    msg = f"Firewall {f['id']} has invalid rule source: {rule['src']}"
                    errors.append(msg)
                    log_event("validation", msg, source="validator")

        # Validate Links
        for link in topo_config.get('links', []):
            for endpoint in link['endpoints']:
                if endpoint not in device_ids:
                    msg = f"Link endpoint {endpoint} not found in devices."
                    errors.append(msg)
                    log_event("validation", msg, source="validator")
        link_pairs = [tuple(sorted(link['endpoints'])) for link in topo_config.get('links', [])]
        if len(link_pairs) != len(set(link_pairs)):
            msg = "Duplicate links found."
            errors.append(msg)
            log_event("validation", msg, source="validator")

        if errors:
            log_event("validation", "❌ Topology validation failed.", source="validator")
            print("\n❌ Topology validation failed with errors:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            log_event("validation", "✅ Topology validation passed.", source="validator")
            print("✅ Topology validation passed.")

    start_session(yaml_file, topology_summary)

    topo = CustomTopo(topo_config)
    # Build Mininet with OVSController
    from mininet.node import OVSController  # Required for Open vSwitch
    net = Mininet(topo=topo, link=TCLink, controller=OVSController)  # Use OVSController
    net.start()  # Start the network
    # === Auto configure universal IP forwarding & routing ===
    log_event("system", "Starting universal auto-config for routers, firewalls, and hosts", source="auto-config")

    # Routers - enable forwarding, set IPs, static routes
    for router in topo_config.get('routers', []):
        r_node = net.get(router['id'])
        r_node.cmd("sysctl -w net.ipv4.ip_forward=1")
        log_event("system", f"IP forwarding enabled on {router['id']}", source="auto-config")

        for iface in router.get('interfaces', []):
            r_node.cmd(f"ifconfig {iface['name']} {iface['ip']} up")
            log_event("system", f"{router['id']} interface {iface['name']} set to {iface['ip']}", source="auto-config")

        for route in router.get('routes', []):
            r_node.cmd(f"ip route add {route['dest']} via {route['via']}")
            log_event("system", f"Route added on {router['id']}: {route['dest']} via {route['via']}", source="auto-config")

    # Firewalls - enable forwarding, set IPs, rules
    for fw in topo_config.get('firewalls', []):
        fw_node = net.get(fw['id'])
        fw_node.cmd("sysctl -w net.ipv4.ip_forward=1")
        log_event("system", f"IP forwarding enabled on {fw['id']}", source="auto-config")

        for iface in fw.get('interfaces', []):
            fw_node.cmd(f"ifconfig {iface['name']} {iface['ip']} up")
            log_event("system", f"{fw['id']} interface {iface['name']} set to {iface['ip']}", source="auto-config")

        for rule in fw.get('rules', []):
            fw_node.cmd(f"iptables -A FORWARD -s {rule['src']} -j {rule['action']}")
            log_event("system", f"Firewall {fw['id']} rule: {rule['action']} from {rule['src']}", source="auto-config")

    # Hosts - set default route + return routes for resilience
    for host in topo_config.get('hosts', []):
        h_node = net.get(host['id'])
        host_ip_parts = host['ip'].split('/')[0].split('.')

        gateway_ip = None
        for link in topo_config.get('links', []):
            if host['id'] in link['endpoints']:
                peer = [p for p in link['endpoints'] if p != host['id']][0]
                for router in topo_config.get('routers', []):
                    if router['id'] == peer:
                        for iface in router.get('interfaces', []):
                            if iface['ip'].split('.')[0:3] == host_ip_parts[0:3]:
                                gateway_ip = iface['ip'].split('/')[0]
                for fw in topo_config.get('firewalls', []):
                    if fw['id'] == peer:
                        for iface in fw.get('interfaces', []):
                            if iface['ip'].split('.')[0:3] == host_ip_parts[0:3]:
                                gateway_ip = iface['ip'].split('/')[0]

        if gateway_ip:
            h_node.cmd(f"ip route add default via {gateway_ip}")
            log_event("system", f"Default route set on {host['id']} via {gateway_ip}", source="auto-config")
        else:
            log_event("system", f"No gateway found for {host['id']}", source="auto-config")

        # Add return route (fail-proof in case default route doesn't match)
        for peer in topo_config.get('hosts', []):
            if peer['id'] != host['id']:
                subnet = '.'.join(peer['ip'].split('/')[0].split('.')[:3]) + '.0/24'
                h_node.cmd(f"ip route add {subnet} dev {host['id']}-eth0")
                log_event("system", f"Return route added on {host['id']} to {subnet}", source="auto-config")


    # Auto configure routers
    for router in topo_config.get('routers', []):
        r_node = net.get(router['id'])
        r_node.cmd("sysctl -w net.ipv4.ip_forward=1")
        log_event("system", f"IP forwarding enabled on {router['id']}", source="auto-config")

        # Set interface IPs
        for iface in router.get('interfaces', []):
            r_node.cmd(f"ifconfig {iface['name']} {iface['ip']} up")
            log_event("system", f"{router['id']} interface {iface['name']} set to {iface['ip']}", source="auto-config")

        # Add static routes
        for route in router.get('routes', []):
            r_node.cmd(f"ip route add {route['dest']} via {route['via']}")
            log_event("system", f"Route added on {router['id']}: {route['dest']} via {route['via']}", source="auto-config")


    # Auto configure firewalls
    for fw in topo_config.get('firewalls', []):
        fw_node = net.get(fw['id'])
        fw_node.cmd("sysctl -w net.ipv4.ip_forward=1")
        log_event("system", f"IP forwarding enabled on {fw['id']}", source="auto-config")

        # Set firewall interface IPs
        for iface in fw.get('interfaces', []):
            fw_node.cmd(f"ifconfig {iface['name']} {iface['ip']} up")
            log_event("system", f"{fw['id']} interface {iface['name']} set to {iface['ip']}", source="auto-config")

        # Apply firewall rules
        for rule in fw.get('rules', []):
            action = rule['action']
            src_ip = rule.get('src')
            fw_node.cmd(f"iptables -A FORWARD -s {src_ip} -j {action}")
            log_event("system", f"Firewall {fw['id']} rule: {action} from {src_ip}", source="auto-config")

    # # === Auto configure default routes for hosts ===
    # for host in topo_config.get('hosts', []):
    #     h_node = net.get(host['id'])

    #     # Identify the gateway (connected router or firewall)
    #     gateway_ip = None
    #     for link in topo_config.get('links', []):
    #         if host['id'] in link['endpoints']:
    #             other_dev = [dev for dev in link['endpoints'] if dev != host['id']][0]

    #             # Check if the other device is a router or firewall
    #             for router in topo_config.get('routers', []):
    #                 if router['id'] == other_dev:
    #                     # Find IP in same subnet
    #                     for iface in router.get('interfaces', []):
    #                         if iface['ip'].split('/')[0].startswith(host['ip'].split('.')[0]):
    #                             gateway_ip = iface['ip'].split('/')[0]
    #             for fw in topo_config.get('firewalls', []):
    #                 if fw['id'] == other_dev:
    #                     for iface in fw.get('interfaces', []):
    #                         if iface['ip'].split('/')[0].startswith(host['ip'].split('.')[0]):
    #                             gateway_ip = iface['ip'].split('/')[0]

    #     # Apply default route if gateway found
    #     if gateway_ip:
    #         h_node.cmd(f"ip route add default via {gateway_ip}")
    #         log_event("system", f"Default route set on {host['id']} via {gateway_ip}", source="auto-config")
    #     else:
    #         log_event("system", f"No gateway found for host {host['id']}", source="auto-config")

    
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
