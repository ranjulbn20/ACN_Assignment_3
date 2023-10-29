from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI

class CustomTopology(Topo):
    def build(self):
        # Add hubs (broadcast domains)
        s1 = self.addSwitch('s1', cls=Hub)
        s2 = self.addSwitch('s2', cls=Hub)

        # Add hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')

        # Add links
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s2)
        self.addLink(h5, s2)

def create_topology():
    topo = CustomTopology()
    net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip='127.0.0.1'))
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    create_topology()
