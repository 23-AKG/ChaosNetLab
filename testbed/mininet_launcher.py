import yaml
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

def launch_topology(yaml_file):
    with open(yaml_file, 'r') as f:
        topo_config = yaml.safe_load(f)

    topo = CustomTopo(topo_config)
    net = Mininet(topo=topo, link=TCLink, controller=OVSController)
    net.addController('c0')

    net.start()
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
