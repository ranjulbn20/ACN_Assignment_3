from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.monitor import Monitor

class CustomFirewallMonitor(Monitor):
    def __init__(self, switch):
        super().__init__(switch)
        self.h3_packet_count = 0

    def packet_in(self, dpid, packet):
        super().packet_in(dpid, packet)

        # Count all packets coming from host H3
        if packet.src == 'h3':
            self.h3_packet_count += 1

        # Implement firewall rules
        if packet.src == 'h2' and packet.dst == 'h3' or packet.src == 'h3' and packet.dst == 'h5' or packet.src == 'h1' and packet.dst == 'h4':
            self.drop(dpid, packet)

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
        self.addLink(s1, s2, cls=TCLink, monitor=CustomFirewallMonitor(s1))
        self.addLink(h1, s1, cls=TCLink)
        self.addLink(h2, s1, cls=TCLink)
        self.addLink(h3, s1, cls=TCLink)
        self.addLink(h4, s2, cls=TCLink)
        self.addLink(h5, s2, cls=TCLink)

topos = { 'mytopo' : ( lambda: CustomTopology() )}

if __name__ == '__main__':
    net = Mininet(topo=CustomTopology(), controller=RemoteController, link=TCLink)
    net.start()

    # Install firewall rules on switches
    net['s1'].cmd('ovs-ofctl add-flow s1 in_port=2,dl_src=%s,dl_dst=%s actions=drop' % (h2.MAC(), h3.MAC()))
    net['s1'].cmd('ovs-ofctl add-flow s1 in_port=3,dl_src=%s,dl_dst=%s actions=drop' % (h3.MAC(), h5.MAC()))
    net['s1'].cmd('ovs-ofctl add-flow s1 in_port=1,dl_src=%s,dl_dst=%s actions=drop' % (h1.MAC(), h4.MAC()))

    CLI(net)

    net.stop()
