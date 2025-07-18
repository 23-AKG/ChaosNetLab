import yaml
import socket
import threading
import json
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSController

class CustomTopo(Topo):
    def build(self, topo_config):
        switches = {}
        hosts = {}

        for sw in topo_config.get('switches', []):
            switches[sw['id']] = self.addSwitch(sw['id'])

        for host in topo_config.get('hosts', []):
            hosts[host['id']] = self.addHost(host['id'], ip=host['ip'])

        for link in topo_config.get('links', []):
            src, dst = link['endpoints']
            params = {
                'delay': link.get('delay', '0ms'),
                'loss': float(link.get('loss', '0').replace('%', ''))
            }
            self.addLink(src, dst, cls=TCLink, **params)

def fault_listener(net, host='127.0.0.1', port=9999):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"[CTRL] Listening for fault commands on {host}:{port}...")

    while True:
        client, addr = server.accept()
        data = client.recv(1024).decode('utf-8')
        try:
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

            else:
                result = f"Unsupported fault type: {fault_type}"

            print(f"[INJECTED] {fault_type} on {target} -> {result.strip()}")
            client.send(f"✅ Injected {fault_type} on {target}".encode())
        except Exception as e:
            print(f"[ERROR] {e}")
            client.send(f"❌ Failed: {str(e)}".encode())
        client.close()

def launch_topology(yaml_file):
    with open(yaml_file, 'r') as f:
        topo_config = yaml.safe_load(f)

    topo = CustomTopo(topo_config)
    net = Mininet(topo=topo, link=TCLink, controller=OVSController)
    net.addController('c0')

    net.start()
    threading.Thread(target=fault_listener, args=(net,), daemon=True).start()
    print("[*] Network started. Running CLI...")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    import sys
    setLogLevel('info')
    if len(sys.argv) < 2:
        print("Usage: sudo python3 mininet_launcher.py <topology.yaml>")
    else:
        launch_topology(sys.argv[1])
