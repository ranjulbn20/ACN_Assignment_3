from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet.packet import Packet
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

class LoadBalancer(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    virtual_ip = "10.0.0.42"
    servers = ["10.0.0.4", "10.0.0.5"]  # List of server IP addresses
    next_server_index = 0

    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        etherFrame = pkt.get_protocol(ethernet.ethernet)

        if etherFrame.ethertype == ether_types.ETH_TYPE_ARP:
            self.add_flow(dp, pkt, ofp_parser, ofp, in_port)
            self.arp_response(dp, pkt, etherFrame, ofp_parser, ofp, in_port)
            return

    def arp_response(self, datapath, packet, etherFrame, ofp_parser, ofp, in_port):
        arpPacket = packet.get_protocol(arp.arp)
        dstIp = arpPacket.src_ip
        srcIp = arpPacket.dst_ip
        dstMac = etherFrame.src

        if dstIp not in self.servers:
            # Select the next server in the round-robin fashion
            target_server = self.servers[self.next_server_index]
            self.next_server_index = (self.next_server_index + 1) % len(self.servers
        else:
            target_server = dstIp

        srcMac = self.ip_to_mac[target_server]

        e = ethernet.ethernet(dstMac, srcMac, ether_types.ETH_TYPE_ARP)
        a = arp.arp(1, 0x0800, 6, 4, 2, srcMac, srcIp, dstMac, dstIp)
        p = Packet()
        p.add_protocol(e)
        p.add_protocol(a)
        p.serialize()

        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_IN_PORT)]
        out = ofp_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofp.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=p.data
        )
        datapath.send_msg(out)

    def add_flow(self, datapath, packet, ofp_parser, ofp, in_port):
        srcIp = packet.get_protocol(arp.arp).src_ip

        if srcIp in self.servers:
            return

        # Select the next server in the round-robin fashion
        target_server = self.servers[self.next_server_index]
        self.next_server_index = (self.next_server_index + 1) % len(self.servers)

        match = ofp_parser.OFPMatch(in_port=in_port,
                                    ipv4_dst=self.virtual_ip,
                                    eth_type=0x0800)
        actions = [ofp_parser.OFPActionSetField(ipv4_dst=target_server),
                   ofp_parser.OFPActionOutput(self.ip_to_port[target_server])]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)
        
        mod = ofp_parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            buffer_id=ofp.OFP_NO_BUFFER,
            match=match,
            instructions=inst)

        datapath.send_msg(mod)

        match = ofp_parser.OFPMatch(in_port=self.ip_to_port[target_server],
                                    ipv4_src=target_server,
                                    ipv4_dst=srcIp,
                                    eth_type=0x0800)
        actions = [ofp_parser.OFPActionSetField(ipv4_src=self.virtual_ip),
                   ofp_parser.OFPActionOutput(in_port)]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)

        mod = ofp_parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            buffer_id=ofp.OFP_NO_BUFFER,
            match=match,
            instructions=inst)

        datapath.send_msg(mod)
