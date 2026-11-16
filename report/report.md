# CS 145 Project 2: Intra-Domain Routing Algorithms

## Author and collaborators
### Author name
Dam Duc Tuyen - 24020683

### Collaborators
None

## Report
### 1. Distance-Vector Routing (`DVrouter.py`)
- **Routing Data Structures**:
  - `active_links`: maps port to neighbor address and link cost.
  - `distance_vector`: maps destination address to lowest cost (initialized with `self.addr: 0`).
  - `forwarding_table`: maps destination address to outgoing port.
  - `next_hop`: tracks next-hop node address for each destination.
  - `neighbor_vectors`: stores latest distance vector advertisements received from direct neighbors.
- **Bellman-Ford Algorithm**:
  - Computes shortest paths across all known destinations using direct links and neighbors' advertised distances:
    $D(x) = \min_v \{ c(u, v) + D_v(x) \}$.
  - Uses `INFINITY = 16` to handle count-to-infinity bounded convergence.
  - Hysteresis / tie-breaking prefers the current next-hop to avoid route oscillation.
- **Split Horizon with Poisoned Reverse**:
  - When broadcasting distance vector to neighbor $v$, if our path to destination $d$ routes through $v$ (`next_hop[d] == v`), we advertise cost `INFINITY` (16) to $v$.
  - This eliminates two-node routing loops and speeds up failure convergence.
- **Link Failure and Topology Changes**:
  - `handle_new_link` and `handle_remove_link` update local link state, trigger Bellman-Ford recomputation, and immediately broadcast the updated distance vector.
  - Periodic heartbeat in `handle_time` advertises distance vectors every `heartbeat_time` ms.

### 2. Link-State Routing (`LSrouter.py`)
- **Link State Database (LSDB)**:
  - Stores `origin_addr -> {"seq": seq_num, "links": {neighbor: cost}}`.
  - Routers maintain a monotonically increasing `sequence_number` to ensure fresh LSPs supersede older or duplicate advertisements.
- **Reliable Flooding**:
  - When a router's local links change or on periodic heartbeat, it increments its sequence number and floods its LSP to all active neighbors.
  - When receiving an LSP, if `seq <= stored_seq`, the packet is dropped immediately to prevent broadcast storms and loops.
  - Otherwise, the LSDB is updated and the packet is forwarded out all other active ports (split-horizon flooding).
  - On new link addition (`handle_new_link`), the router originates a fresh LSP and synchronizes all known LSDB entries across the new link.
- **Dijkstra's Shortest Path Algorithm**:
  - Implemented using Python's `heapq` priority queue over the graph defined by the LSDB.
  - Identifies the first-hop outgoing port for every reachable destination to populate `forwarding_table`.
  - Hysteresis tie-breaking keeps routes stable under equal-cost multipath scenarios.

## Citations
- Python standard library documentation (`heapq`, `json`).
- CS 145 / COS 461 Lecture Slides on Intra-Domain Routing (Distance Vector, Link State, Bellman-Ford, Dijkstra, Split Horizon & Poisoned Reverse).

## Grading notes (if any)
Passed all 6 network simulation test cases with 100% correct routes on both Distance Vector (`DV`) and Link State (`LS`):
- `01_small_net.json` (DV: PASS, LS: PASS)
- `02_small_net_events.json` (DV: PASS, LS: PASS)
- `03_pg244_net.json` (DV: PASS, LS: PASS)
- `04_pg244_net_events.json` (DV: PASS, LS: PASS)
- `05_pg242_net.json` (DV: PASS, LS: PASS)
- `06_pg242_net_events.json` (DV: PASS, LS: PASS)

## Extra credit attempted (if any)
Implemented both Distance-Vector (`DVrouter.py`) and Link-State (`LSrouter.py`), with all tests passing for both (+20 bonus points).
