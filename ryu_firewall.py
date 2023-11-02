from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto.ofproto_v1_3_parser import OFPMatch, OFPFlowMod

class FirewallMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FirewallMonitor, self).__init__(*args, **kwargs)
        self.blocked_hosts = {'h2': 'h3', 'h3': 'h5', 'h1': 'h4'}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto

        # Install firewall rules
        for src_host, dst_host in self.blocked_hosts.items():
            match = OFPMatch(eth_src=src_host, eth_dst=dst_host)
            actions = []
            self.add_flow(datapath, 1, match, actions)

        # Monitor packets from H3 on S1
        if datapath.id == 1:
            match = OFPMatch(eth_src='h3')
            actions = []
            self.add_flow(datapath, 2, match, actions, priority=2)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath, buffer_id=buffer_id, priority=priority,
                match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority, match=match,
                instructions=inst)

        datapath.send_msg(mod)

def main():
    from ryu.lib import hub
    app_manager.require_app('ryu.app.simple_switch_13')
    app_manager.require_app('ryu.app.ofctl_rest')

    hub.spawn(app_manager.run, sys.argv)

if __name__ == '__main__':
    main()
