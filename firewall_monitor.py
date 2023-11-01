from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI

class CustomTopology(Topo):
    def build(self):
        # Add switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Add hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')

        # Add links
        self.addLink(s1, s2)
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s2)
        self.addLink(h5, s2)

topos = {'mytopo': (lambda: CustomTopology())}

# Create the network
net = Mininet(topo=CustomTopology(), controller=RemoteController)

# Start the network
net.start()

# Add OpenFlow rules to implement the firewall
s1 = net.get('s1')
s2 = net.get('s2')

# Block communication between H2 and H3 with H5 on switch S1
s1.dpctl('add-flow in_port=1,dl_dst=' + h2.MAC() + ',actions=drop')
s1.dpctl('add-flow in_port=1,dl_dst=' + h3.MAC() + ',actions=drop')
s1.dpctl('add-flow in_port=1,dl_dst=' + h5.MAC() + ',actions=drop')

# Block communication between H1 and H4 on switch S2
s2.dpctl('add-flow in_port=1,dl_dst=' + h1.MAC() + ',actions=drop')
s2.dpctl('add-flow in_port=1,dl_dst=' + h4.MAC() + ',actions=drop')

# Count packets coming from H3 on switch S1
s1.dpctl('add-flow in_port=3,actions=controller')

# Start the Mininet CLI
CLI(net)

# Stop the network
net.stop()
