
from mininet.net import Containernet
from mininet.node import Controller
from containernet.node import DockerHost
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

setLogLevel('info')

def setup():
    net = Containernet(controller=Controller)
    print("*** Adding controller")
    net.addController('c0')

    print("*** Adding Docker containers")
    web = net.addDocker('webserver', dimage="webserver:latest", ip='10.0.0.2')
    inj = net.addDocker('injector', dimage="injector:latest", ip='10.0.0.3')

    print("*** Adding switch and links")
    s1 = net.addSwitch('s1')
    net.addLink(web, s1, delay="20ms")
    net.addLink(inj, s1)

    print("*** Starting network")
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setup()
