####################################################
# DVrouter.py
# Name: Dam Duc Tuyen
# HUID: 24020683
#####################################################

import json
from router import Router
from packet import Packet


class DVrouter(Router):
    """Distance vector routing protocol implementation."""

    INFINITY = 16

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # Local active link table: port -> {"endpoint": endpoint_addr, "cost": link_cost}
        self.active_links = {}
        # Reverse mapping: endpoint_addr -> port
        self.endpoint_ports = {}

        # Distance vector: destination -> cost
        self.distance_vector = {self.addr: 0}
        # Forwarding table: destination -> outgoing port
        self.forwarding_table = {}
        # Next hop table: destination -> next hop node address
        self.next_hop = {self.addr: self.addr}

        # Stored distance vectors received from adjacent neighbors:
        # neighbor_addr -> {destination: advertised_cost}
        self.neighbor_vectors = {}

    def _recompute_routes(self):
        """Run Bellman-Ford algorithm to compute shortest paths.
        
        Returns True if the distance vector or next-hop mapping changed.
        """
        all_dests = set(self.distance_vector.keys())
        all_dests.add(self.addr)
        all_dests.update(self.endpoint_ports.keys())
        for nbr_vec in self.neighbor_vectors.values():
            all_dests.update(nbr_vec.keys())

        updated_dv = {self.addr: 0}
        updated_ft = {}
        updated_next_hop = {self.addr: self.addr}

        for dest in all_dests:
            if dest == self.addr:
                continue

            lowest_cost = self.INFINITY
            chosen_port = None
            chosen_next_hop = None

            for port, link_info in self.active_links.items():
                nbr = link_info["endpoint"]
                c_direct = link_info["cost"]

                # Case 1: Direct link to the destination
                if nbr == dest:
                    if c_direct < lowest_cost:
                        lowest_cost = c_direct
                        chosen_port = port
                        chosen_next_hop = nbr
                    elif c_direct == lowest_cost and self.next_hop.get(dest) == nbr:
                        chosen_port = port
                        chosen_next_hop = nbr

                # Case 2: Route via neighbor nbr
                nbr_dv = self.neighbor_vectors.get(nbr)
                if nbr_dv is not None and dest in nbr_dv:
                    adv_cost = nbr_dv[dest]
                    if adv_cost < self.INFINITY:
                        total_cost = c_direct + adv_cost
                        if total_cost < lowest_cost:
                            lowest_cost = total_cost
                            chosen_port = port
                            chosen_next_hop = nbr
                        elif total_cost == lowest_cost and self.next_hop.get(dest) == nbr:
                            chosen_port = port
                            chosen_next_hop = nbr

            if lowest_cost < self.INFINITY:
                updated_dv[dest] = lowest_cost
                updated_ft[dest] = chosen_port
                updated_next_hop[dest] = chosen_next_hop
            else:
                updated_dv[dest] = self.INFINITY

        has_changed = (updated_dv != self.distance_vector) or (updated_next_hop != self.next_hop)
        self.distance_vector = updated_dv
        self.forwarding_table = updated_ft
        self.next_hop = updated_next_hop
        return has_changed

    def _broadcast_distance_vector(self):
        """Send distance vector to all active neighbors with split-horizon / poisoned reverse."""
        for port, link_info in self.active_links.items():
            nbr = link_info["endpoint"]

            # Construct poisoned vector for neighbor nbr
            vector_to_send = {}
            for dest, cost in self.distance_vector.items():
                if dest == self.addr:
                    vector_to_send[dest] = 0
                elif self.next_hop.get(dest) == nbr:
                    # Poisoned reverse: poison route advertised to our next-hop
                    vector_to_send[dest] = self.INFINITY
                else:
                    vector_to_send[dest] = cost

            payload = json.dumps(vector_to_send)
            pkt = Packet(Packet.ROUTING, self.addr, nbr, content=payload)
            self.send(port, pkt)

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dest = packet.dst_addr
            if dest in self.forwarding_table:
                out_port = self.forwarding_table[dest]
                self.send(out_port, packet)
        elif packet.is_routing:
            sender = packet.src_addr
            try:
                received_vector = json.loads(packet.content)
            except Exception:
                return

            if self.neighbor_vectors.get(sender) != received_vector:
                self.neighbor_vectors[sender] = received_vector
                if self._recompute_routes():
                    self._broadcast_distance_vector()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link addition."""
        self.active_links[port] = {"endpoint": endpoint, "cost": cost}
        self.endpoint_ports[endpoint] = port
        self._recompute_routes()
        self._broadcast_distance_vector()

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.active_links:
            endpoint = self.active_links[port]["endpoint"]
            del self.active_links[port]
            self.endpoint_ports.pop(endpoint, None)
            self.neighbor_vectors.pop(endpoint, None)
            self._recompute_routes()
            self._broadcast_distance_vector()

    def handle_time(self, time_ms):
        """Handle current time and send periodic heartbeat routing packets."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_distance_vector()

    def __repr__(self):
        """Representation for debugging."""
        return f"DVrouter(addr={self.addr}, table={self.forwarding_table})"
