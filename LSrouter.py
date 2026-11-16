####################################################
# LSrouter.py
# Name: Dam Duc Tuyen
# HUID: 24020683
#####################################################

import heapq
import json
from router import Router
from packet import Packet


class LSrouter(Router):
    """Link state routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # Sequence number for this router's Link State Packets (LSP)
        self.sequence_number = 0

        # Local active links: port -> {"endpoint": endpoint_addr, "cost": link_cost}
        self.active_links = {}
        # Reverse mapping: endpoint_addr -> port
        self.endpoint_ports = {}

        # Link State Database (LSDB): origin_addr -> {"seq": seq_num, "links": {neighbor_addr: cost}}
        self.ls_database = {}

        # Forwarding table: destination -> outgoing port
        self.forwarding_table = {}

    def _get_local_links_dict(self):
        """Return dict of neighbor_addr -> cost for all current local links."""
        return {info["endpoint"]: info["cost"] for info in self.active_links.values()}

    def _run_dijkstra(self):
        """Compute shortest path tree from self.addr to all reachable destinations using Dijkstra's algorithm."""
        # Ensure our own latest link state is reflected in the database
        self.ls_database[self.addr] = {
            "seq": self.sequence_number,
            "links": self._get_local_links_dict(),
        }

        distances = {self.addr: 0}
        first_hop_info = {}  # dest_addr -> (next_hop_node, outgoing_port)
        visited = set()
        priority_queue = [(0, self.addr)]

        while priority_queue:
            dist_u, u = heapq.heappop(priority_queue)
            if u in visited:
                continue
            visited.add(u)

            if u == self.addr:
                # Direct links from self.addr
                for port, info in self.active_links.items():
                    v = info["endpoint"]
                    cost = info["cost"]
                    new_dist = dist_u + cost
                    if (v not in distances) or (new_dist < distances[v]):
                        distances[v] = new_dist
                        first_hop_info[v] = (v, port)
                        heapq.heappush(priority_queue, (new_dist, v))
                    elif new_dist == distances[v]:
                        # Hysteresis: keep stable port if already chosen
                        if self.forwarding_table.get(v) == port:
                            first_hop_info[v] = (v, port)
            else:
                record = self.ls_database.get(u)
                if not record:
                    continue
                u_edges = record.get("links", {})
                for v, cost in u_edges.items():
                    new_dist = dist_u + cost
                    if (v not in distances) or (new_dist < distances[v]):
                        distances[v] = new_dist
                        first_hop_info[v] = first_hop_info[u]
                        heapq.heappush(priority_queue, (new_dist, v))
                    elif new_dist == distances[v]:
                        if v in first_hop_info and self.forwarding_table.get(v) == first_hop_info[u][1]:
                            first_hop_info[v] = first_hop_info[u]

        # Update forwarding table from first hop outgoing ports
        new_forwarding_table = {}
        for dest, (next_hop_node, out_port) in first_hop_info.items():
            if dest != self.addr:
                new_forwarding_table[dest] = out_port

        self.forwarding_table = new_forwarding_table

    def _broadcast_own_lsp(self):
        """Originate and broadcast a fresh LSP for this router to all active neighbors."""
        self.sequence_number += 1
        links_data = self._get_local_links_dict()
        self.ls_database[self.addr] = {
            "seq": self.sequence_number,
            "links": links_data,
        }
        self._run_dijkstra()

        lsp_payload = json.dumps({
            "origin": self.addr,
            "seq": self.sequence_number,
            "links": links_data,
        })

        for port, info in self.active_links.items():
            pkt = Packet(Packet.ROUTING, self.addr, info["endpoint"], content=lsp_payload)
            self.send(port, pkt)

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dest = packet.dst_addr
            if dest in self.forwarding_table:
                out_port = self.forwarding_table[dest]
                self.send(out_port, packet)
        elif packet.is_routing:
            try:
                data = json.loads(packet.content)
                origin = data["origin"]
                seq = data["seq"]
                links = data["links"]
            except Exception:
                return

            # Check if this LSP is newer than what we already know
            known = self.ls_database.get(origin)
            if known is not None and seq <= known["seq"]:
                return  # Disregard old or duplicate LSP

            has_link_change = (known is None) or (known["links"] != links)
            self.ls_database[origin] = {"seq": seq, "links": links}

            if has_link_change:
                self._run_dijkstra()

            # Reliable flooding: forward the LSP to all other active neighbors
            for out_port, info in self.active_links.items():
                if out_port != port:
                    fwd_pkt = Packet(Packet.ROUTING, self.addr, info["endpoint"], content=packet.content)
                    self.send(out_port, fwd_pkt)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link addition."""
        self.active_links[port] = {"endpoint": endpoint, "cost": cost}
        self.endpoint_ports[endpoint] = port

        # Originate fresh LSP and broadcast to all neighbors
        self._broadcast_own_lsp()

        # Synchronize our existing LSDB knowledge to the newly connected neighbor
        for orig, record in list(self.ls_database.items()):
            if orig != self.addr:
                sync_payload = json.dumps({
                    "origin": orig,
                    "seq": record["seq"],
                    "links": record["links"],
                })
                sync_pkt = Packet(Packet.ROUTING, self.addr, endpoint, content=sync_payload)
                self.send(port, sync_pkt)

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.active_links:
            endpoint = self.active_links[port]["endpoint"]
            del self.active_links[port]
            self.endpoint_ports.pop(endpoint, None)
            self._broadcast_own_lsp()

    def handle_time(self, time_ms):
        """Handle current time and send periodic heartbeat routing packets."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_own_lsp()

    def __repr__(self):
        """Representation for debugging."""
        return f"LSrouter(addr={self.addr}, table={self.forwarding_table})"
