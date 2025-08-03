from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel
import sys
import yaml
import os

# Load topology YAML to figure out expected tests
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPO_FILE = os.path.join(PROJECT_ROOT, "topology", "complex_topology2.yaml")

def load_topology(yaml_path):
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def ping_test(net, src, dst_ip, expected="PASS"):
    src_host = net.get(src)
    output = src_host.cmd(f"ping -c 2 {dst_ip}")
    if "0% packet loss" in output:
        if expected == "PASS":
            print(f"✅ PASS: {src} can reach {dst_ip}")
            return True
        else:
            print(f"❌ FAIL: {src} should be blocked from {dst_ip}")
            return False
    else:
        if expected == "BLOCK":
            print(f"✅ PASS: {src} blocked from {dst_ip}")
            return True
        else:
            print(f"❌ FAIL: {src} cannot reach {dst_ip}")
            return False

def main():
    setLogLevel('info')

    # Attach to the running Mininet instance
    net = Mininet(controller=None)  # Will attach to existing net
    topo = load_topology(TOPO_FILE)

    print("\n=== BASIC CONNECTIVITY ===")
    for h in topo.get("hosts", []):
        for target in topo.get("hosts", []):
            if h["id"] != target["id"]:
                ping_test(net, h["id"], target["ip"].split("/")[0], expected="PASS")

    print("\n=== FIREWALL ENFORCEMENT ===")
    for fw in topo.get("firewalls", []):
        for rule in fw.get("rules", []):
            src_ip = rule["src"]
            action = rule["action"]
            # Find which host has that IP
            src_host_id = None
            dst_host_id = None
            for h in topo.get("hosts", []):
                if h["ip"].startswith(src_ip):
                    src_host_id = h["id"]
            # Just test blocked src against all others
            for h in topo.get("hosts", []):
                if h["id"] != src_host_id:
                    ping_test(net, src_host_id, h["ip"].split("/")[0],
                              expected="BLOCK" if action == "DROP" else "PASS")

    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    main()
