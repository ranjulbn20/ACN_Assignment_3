from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
from ryu.lib.mac import haddr_to_int
from ryu.lib.packet.ether_types import ETH_TYPE_IP
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    virtual_ip = '10.0.0.42'  # The virtual server IP

    h4_ip = '10.0.0.4'
    h4_mac = '00:00:00:00:00:04'
    switch_port = 1
    h5_ip = '10.0.0.5'
    h5_mac = '00:00:00:00:00:05'
    switch_port = 1

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst_mac = eth.dst
        src_mac = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid,
                         src_mac, dst_mac, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src_mac] = in_port

        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port, eth_dst=dst_mac, eth_src=src_mac)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 10, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 10, match, actions)

        if self.handle_packets(eth.ethertype, datapath, pkt, in_port, parser, dst_mac, src_mac):
            return

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def handle_packets(self, ethtype, datapath, pkt, in_port, parser, dst_mac, src_mac):
        handle = False
        if ethtype == ETH_TYPE_IP:
            ip = pkt.get_protocol(ipv4.ipv4)
            if ip.dst == self.virtual_ip:
                handle = True
                if dst_mac == self.h4_mac:
                    server_dst_ip = self.h4_ip
                    server_out_port = self.switch_port
                else:
                    server_dst_ip = self.h5_ip
                    server_out_port = self.switch_port

                # Route to server
                match = parser.OFPMatch(in_port=in_port, eth_type=ETH_TYPE_IP, ip_proto=ip.proto,
                                        ipv4_dst=self.virtual_ip)

                actions = [parser.OFPActionSetField(ipv4_dst=server_dst_ip),
                           parser.OFPActionOutput(server_out_port)]

                self.add_flow(datapath, 20, match, actions)

                # Reverse route from server
                match = parser.OFPMatch(in_port=server_out_port, eth_type=ETH_TYPE_IP,
                                        ip_proto=ip.proto,
                                        ipv4_src=server_dst_ip,
                                        eth_dst=src_mac)
                actions = [parser.OFPActionSetField(ipv4_src=self.virtual_ip),
                           parser.OFPActionOutput(in_port)]

                self.add_flow(datapath, 20, match, actions)

        elif ethtype == ether_types.ETH_TYPE_ARP:
            arp_obj = pkt.get_protocol(arp.arp)

            if arp_obj.dst_ip == self.virtual_ip and arp_obj.opcode == arp.ARP_REQUEST:
                arp_target_ip = arp_obj.src_ip
                arp_target_mac = arp_obj.src_mac
                src_ip = self.virtual_ip

                if haddr_to_int(arp_target_mac) % 2 == 1:
                    src_mac = self.h4_mac
                else:
                    src_mac = self.h5_mac

                replypkt = packet.Packet()
                replypkt.add_protocol(
                    ethernet.ethernet(
                        dst=dst_mac, src=src_mac, ethertype=ether_types.ETH_TYPE_ARP)
                )
                replypkt.add_protocol(
                    arp.arp(opcode=arp.ARP_REPLY, src_mac=src_mac, src_ip=src_ip,
                            dst_mac=arp_target_mac, dst_ip=arp_target_ip)
                )
                replypkt.serialize()

                actions = [parser.OFPActionOutput(in_port)]
                packet_out = parser.OFPPacketOut(datapath=datapath, in_port=(datapath.ofproto).OFPP_ANY,
                                                data=replypkt.data, actions=actions, buffer_id=0xffffffff)
                datapath.send_msg(packet_out)
                handle = True

        return handle
