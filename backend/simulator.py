import heapq
import random
import time
import math
from typing import Dict, List, Any, Optional

class NetworkSimulator:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.links: Dict[str, Dict[str, Any]] = {}
        self.active_template = "enterprise_campus"
        self.simulation_time = 0
        self.active_traffic_flows: List[Dict[str, Any]] = []
        self.incidents_log: List[Dict[str, Any]] = []
        self.digital_twin_mode = "LIVE_SYNC" # LIVE_SYNC or ISOLATED_SANDBOX
        self.drift_percentage = 0.0
        
        # Initialize default topology
        self.load_template("enterprise_campus")

    def reset(self):
        self.nodes.clear()
        self.links.clear()
        self.active_traffic_flows.clear()
        self.incidents_log.clear()

    def add_node(self, node_id: str, name: str, node_type: str, ip: str, x: float = 0, y: float = 0, config: Optional[Dict] = None):
        self.nodes[node_id] = {
            "id": node_id,
            "name": name,
            "type": node_type, # router, switch, firewall, server, client, cloud
            "ip": ip,
            "status": "active", # active, degraded, failed
            "cpu_load": round(random.uniform(12, 35), 1),
            "ram_load": round(random.uniform(20, 45), 1),
            "x": x,
            "y": y,
            "interfaces": [
                {"name": "eth0", "ip": ip, "status": "up", "speed": "10Gbps"},
                {"name": "eth1", "ip": f"192.168.{random.randint(10, 99)}.1", "status": "up", "speed": "1Gbps"}
            ],
            "routing_table": [],
            "config": config or {
                "hostname": name,
                "domain": "enterprise.local",
                "ospf_area": "0.0.0.0",
                "vlan": 10
            }
        }
        self.update_routing_tables()

    def add_link(self, link_id: str, source: str, target: str, bandwidth: int = 1000, latency: float = 2.0, loss: float = 0.0):
        self.links[link_id] = {
            "id": link_id,
            "source": source,
            "target": target,
            "bandwidth": bandwidth, # Mbps
            "latency": latency, # ms
            "loss": loss, # %
            "status": "active", # active, congested, down
            "utilization": round(random.uniform(15, 45), 1), # %
            "throughput": round(random.uniform(100, 450), 1) # Mbps
        }
        self.update_routing_tables()

    def load_template(self, template_name: str):
        self.reset()
        self.active_template = template_name

        if template_name == "enterprise_campus":
            # Edge & Core
            self.add_node("r1", "Core-Router-1", "router", "10.0.0.1", 400, 100)
            self.add_node("r2", "Core-Router-2", "router", "10.0.0.2", 600, 100)
            self.add_node("fw1", "Edge-Firewall", "firewall", "10.0.0.254", 500, 30)
            self.add_node("cloud1", "ISP-Internet-Cloud", "cloud", "8.8.8.8", 500, -60)

            # Switches
            self.add_node("sw1", "Dist-Switch-A", "switch", "192.168.1.1", 300, 240)
            self.add_node("sw2", "Dist-Switch-B", "switch", "192.168.2.1", 700, 240)
            self.add_node("sw3", "Access-Switch-1", "switch", "192.168.10.1", 200, 380)
            self.add_node("sw4", "Access-Switch-2", "switch", "192.168.20.1", 800, 380)

            # Servers & Endpoints
            self.add_node("srv1", "App-Server-01", "server", "10.0.100.10", 450, 240)
            self.add_node("srv2", "DB-Cluster-Main", "server", "10.0.100.20", 550, 240)
            self.add_node("cli1", "Finance-Workstation", "client", "192.168.10.50", 150, 500)
            self.add_node("cli2", "HR-Workstation", "client", "192.168.20.88", 850, 500)

            # Links
            self.add_link("l_cloud_fw", "cloud1", "fw1", 10000, 5.0, 0.0)
            self.add_link("l_fw_r1", "fw1", "r1", 10000, 0.5, 0.0)
            self.add_link("l_fw_r2", "fw1", "r2", 10000, 0.5, 0.0)
            self.add_link("l_r1_r2", "r1", "r2", 10000, 0.2, 0.0)

            self.add_link("l_r1_sw1", "r1", "sw1", 1000, 1.0, 0.0)
            self.add_link("l_r1_sw2", "r1", "sw2", 1000, 1.2, 0.0)
            self.add_link("l_r2_sw1", "r2", "sw1", 1000, 1.2, 0.0)
            self.add_link("l_r2_sw2", "r2", "sw2", 1000, 1.0, 0.0)

            self.add_link("l_r1_srv1", "r1", "srv1", 10000, 0.4, 0.0)
            self.add_link("l_r2_srv2", "r2", "srv2", 10000, 0.4, 0.0)

            self.add_link("l_sw1_sw3", "sw1", "sw3", 1000, 1.5, 0.0)
            self.add_link("l_sw2_sw4", "sw2", "sw4", 1000, 1.5, 0.0)

            self.add_link("l_sw3_cli1", "sw3", "cli1", 100, 2.0, 0.0)
            self.add_link("l_sw4_cli2", "sw4", "cli2", 100, 2.0, 0.0)

        elif template_name == "spine_leaf_datacenter":
            # Spine Switches
            self.add_node("spine1", "Spine-Router-01", "router", "172.16.0.1", 350, 100)
            self.add_node("spine2", "Spine-Router-02", "router", "172.16.0.2", 650, 100)

            # Leaf Switches
            self.add_node("leaf1", "Leaf-Switch-01", "switch", "172.16.1.1", 200, 260)
            self.add_node("leaf2", "Leaf-Switch-02", "switch", "172.16.1.2", 400, 260)
            self.add_node("leaf3", "Leaf-Switch-03", "switch", "172.16.1.3", 600, 260)
            self.add_node("leaf4", "Leaf-Switch-04", "switch", "172.16.1.4", 800, 260)

            # Servers
            self.add_node("srv_web1", "WebNode-Alpha", "server", "10.20.1.10", 180, 440)
            self.add_node("srv_web2", "WebNode-Beta", "server", "10.20.1.11", 380, 440)
            self.add_node("srv_db1", "Postgres-Primary", "server", "10.20.2.20", 600, 440)
            self.add_node("srv_redis", "Redis-Cache-Cluster", "server", "10.20.2.30", 820, 440)

            # Fully Mesh Spine-Leaf Links
            for spine in ["spine1", "spine2"]:
                for leaf in ["leaf1", "leaf2", "leaf3", "leaf4"]:
                    self.add_link(f"l_{spine}_{leaf}", spine, leaf, 40000, 0.3, 0.0)

            self.add_link("l_l1_w1", "leaf1", "srv_web1", 10000, 0.5, 0.0)
            self.add_link("l_l2_w2", "leaf2", "srv_web2", 10000, 0.5, 0.0)
            self.add_link("l_l3_db1", "leaf3", "srv_db1", 10000, 0.5, 0.0)
            self.add_link("l_l4_redis", "leaf4", "srv_redis", 10000, 0.5, 0.0)

        elif template_name == "isp_backbone":
            # BGP Autonomous Systems
            self.add_node("as100_r1", "AS100-Tier1-Core-A", "router", "198.51.100.1", 250, 150)
            self.add_node("as100_r2", "AS100-Tier1-Core-B", "router", "198.51.100.2", 450, 150)
            self.add_node("as200_r1", "AS200-Transit-East", "router", "203.0.113.1", 650, 150)
            self.add_node("as300_r1", "AS300-Global-Gateway", "router", "192.0.2.1", 450, 350)
            self.add_node("ixp_sw", "Internet-Exchange-IXP", "switch", "192.0.2.254", 450, 500)

            self.add_link("l_as100_core", "as100_r1", "as100_r2", 100000, 1.0, 0.0)
            self.add_link("l_as100_as200", "as100_r2", "as200_r1", 40000, 8.5, 0.0)
            self.add_link("l_as100_as300", "as100_r1", "as300_r1", 40000, 12.0, 0.0)
            self.add_link("l_as200_as300", "as200_r1", "as300_r1", 40000, 14.2, 0.0)
            self.add_link("l_as300_ixp", "as300_r1", "ixp_sw", 100000, 0.8, 0.0)

        self.update_routing_tables()
        self.log_incident("INFO", f"Loaded network template '{template_name}' with {len(self.nodes)} nodes and {len(self.links)} links.")

    def log_incident(self, level: str, message: str, node_id: Optional[str] = None):
        event = {
            "timestamp": time.strftime("%H:%M:%S"),
            "level": level, # INFO, WARNING, CRITICAL
            "message": message,
            "node_id": node_id
        }
        self.incidents_log.insert(0, event)
        if len(self.incidents_log) > 100:
            self.incidents_log.pop()

    def update_routing_tables(self):
        # Calculate shortest paths using Dijkstra for all routers
        adj = {}
        for nid in self.nodes:
            adj[nid] = []

        for lid, link in self.links.items():
            if link["status"] == "down":
                continue
            u, v = link["source"], link["target"]
            cost = link["latency"] + (100.0 / max(1, link["bandwidth"]))
            adj[u].append((v, cost, link["id"]))
            adj[v].append((u, cost, link["id"]))

        for nid, node in self.nodes.items():
            if node["status"] == "failed":
                node["routing_table"] = []
                continue

            # Dijkstra from nid
            distances = {n: float('inf') for n in self.nodes}
            next_hops = {n: None for n in self.nodes}
            distances[nid] = 0

            pq = [(0, nid)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > distances[u]:
                    continue

                for v, weight, lid in adj[u]:
                    if distances[u] + weight < distances[v]:
                        distances[v] = distances[u] + weight
                        next_hops[v] = v if u == nid else next_hops[u]
                        heapq.heappush(pq, (distances[v], v))

            routes = []
            for target_id, dist in distances.items():
                if target_id != nid and dist < float('inf'):
                    target_ip = self.nodes[target_id]["ip"]
                    nh_id = next_hops[target_id]
                    nh_ip = self.nodes[nh_id]["ip"] if nh_id else "direct"
                    routes.append({
                        "destination": f"{target_ip}/32",
                        "next_hop": nh_ip,
                        "metric": round(dist, 2),
                        "protocol": "OSPF",
                        "target_node": target_id
                    })
            node["routing_table"] = routes

    def find_path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        if source_id not in self.nodes or target_id not in self.nodes:
            return {"success": False, "reason": "Invalid node ID"}

        if self.nodes[source_id]["status"] == "failed":
            return {"success": False, "reason": f"Source node {source_id} is down"}

        if self.nodes[target_id]["status"] == "failed":
            return {"success": False, "reason": f"Target node {target_id} is down"}

        adj = {}
        for nid in self.nodes:
            adj[nid] = []

        for lid, link in self.links.items():
            if link["status"] == "down":
                continue
            u, v = link["source"], link["target"]
            # Cost factor incorporating latency and packet loss
            cost = link["latency"] * (1 + link["loss"]/10.0) + (100.0 / max(1, link["bandwidth"]))
            adj[u].append((v, cost, lid, link["latency"], link["loss"]))
            adj[v].append((u, cost, lid, link["latency"], link["loss"]))

        distances = {n: float('inf') for n in self.nodes}
        previous = {n: None for n in self.nodes}
        edge_used = {n: None for n in self.nodes}
        distances[source_id] = 0

        pq = [(0, source_id)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > distances[u]:
                continue
            if u == target_id:
                break

            for v, weight, lid, lat, loss in adj[u]:
                if distances[u] + weight < distances[v]:
                    distances[v] = distances[u] + weight
                    previous[v] = u
                    edge_used[v] = (lid, lat, loss)
                    heapq.heappush(pq, (distances[v], v))

        if distances[target_id] == float('inf'):
            return {
                "success": False,
                "reason": "Destination unreachable - path broken due to link or node failure",
                "hops": []
            }

        # Reconstruct path
        path_nodes = []
        path_links = []
        total_latency = 0.0
        total_loss = 0.0
        curr = target_id

        while curr:
            path_nodes.append(curr)
            if previous[curr]:
                lid, lat, loss = edge_used[curr]
                path_links.append(lid)
                total_latency += lat
                total_loss += loss
            curr = previous[curr]

        path_nodes.reverse()
        path_links.reverse()

        return {
            "success": True,
            "path_nodes": path_nodes,
            "path_links": path_links,
            "total_latency_ms": round(total_latency, 2),
            "estimated_loss_percent": round(total_loss, 2),
            "hop_count": len(path_nodes) - 1
        }

    def inject_failure(self, failure_type: str, target_id: str, intensity: float = 1.0) -> Dict[str, Any]:
        """
        Failure Types:
        - 'cut_link': Sever link completely
        - 'crash_node': Turn node off
        - 'inject_latency': Add high ping jitter
        - 'packet_loss': Induce random loss
        - 'ddos_attack': Spike CPU load and link utilization
        """
        if failure_type == "cut_link":
            if target_id in self.links:
                self.links[target_id]["status"] = "down"
                self.links[target_id]["utilization"] = 0
                self.update_routing_tables()
                self.log_incident("CRITICAL", f"FIBER CUT: Link {target_id} ({self.links[target_id]['source']} <-> {self.links[target_id]['target']}) severed!", target_id)
                return {"success": True, "message": f"Link {target_id} cut successfully."}

        elif failure_type == "crash_node":
            if target_id in self.nodes:
                self.nodes[target_id]["status"] = "failed"
                self.nodes[target_id]["cpu_load"] = 0
                self.nodes[target_id]["ram_load"] = 0
                # Shutdown associated links
                for lid, link in self.links.items():
                    if link["source"] == target_id or link["target"] == target_id:
                        link["utilization"] = 0
                self.update_routing_tables()
                self.log_incident("CRITICAL", f"HARDWARE FAILURE: Node {self.nodes[target_id]['name']} ({target_id}) crashed!", target_id)
                return {"success": True, "message": f"Node {target_id} powered off."}

        elif failure_type == "inject_latency":
            if target_id in self.links:
                self.links[target_id]["latency"] += 150.0 * intensity
                self.links[target_id]["status"] = "congested"
                self.update_routing_tables()
                self.log_incident("WARNING", f"LATENCY SPIKE: Link {target_id} latency increased by +{150.0 * intensity}ms.", target_id)
                return {"success": True, "message": f"Latency injected into link {target_id}."}

        elif failure_type == "packet_loss":
            if target_id in self.links:
                self.links[target_id]["loss"] = round(min(100.0, self.links[target_id]["loss"] + 25.0 * intensity), 1)
                self.update_routing_tables()
                self.log_incident("WARNING", f"PACKET DROP: Link {target_id} loss rate set to {self.links[target_id]['loss']}%.", target_id)
                return {"success": True, "message": f"Packet loss injected into link {target_id}."}

        elif failure_type == "ddos_attack":
            if target_id in self.nodes:
                self.nodes[target_id]["cpu_load"] = round(min(100.0, 95.0 + random.uniform(0, 5)), 1)
                self.nodes[target_id]["ram_load"] = round(min(100.0, 90.0 + random.uniform(0, 8)), 1)
                self.nodes[target_id]["status"] = "degraded"
                # Congest linked interfaces
                for lid, link in self.links.items():
                    if link["source"] == target_id or link["target"] == target_id:
                        link["utilization"] = round(random.uniform(92, 99), 1)
                        link["status"] = "congested"
                self.log_incident("CRITICAL", f"SECURITY ALERT: DDoS Attack flood targeting {self.nodes[target_id]['name']}!", target_id)
                return {"success": True, "message": f"DDoS traffic flooded to node {target_id}."}

        return {"success": False, "message": "Target or failure type not found."}

    def heal_all(self):
        for nid, node in self.nodes.items():
            node["status"] = "active"
            node["cpu_load"] = round(random.uniform(15, 35), 1)
            node["ram_load"] = round(random.uniform(22, 45), 1)

        for lid, link in self.links.items():
            link["status"] = "active"
            link["latency"] = max(0.5, round(random.uniform(0.5, 3.0), 1))
            link["loss"] = 0.0
            link["utilization"] = round(random.uniform(15, 40), 1)

        self.update_routing_tables()
        self.log_incident("INFO", "RECOVERY: Network fully restored to optimal state.")
        return {"success": True, "message": "All network elements restored to healthy state."}

    def tick_telemetry(self):
        self.simulation_time += 1

        # Simulate dynamic telemetry oscillations
        for nid, node in self.nodes.items():
            if node["status"] == "active":
                node["cpu_load"] = round(max(5.0, min(100.0, node["cpu_load"] + random.uniform(-2.5, 2.5))), 1)
                node["ram_load"] = round(max(10.0, min(100.0, node["ram_load"] + random.uniform(-1.0, 1.0))), 1)

        for lid, link in self.links.items():
            if link["status"] == "active":
                link["utilization"] = round(max(5.0, min(95.0, link["utilization"] + random.uniform(-3.5, 3.5))), 1)
                link["throughput"] = round((link["bandwidth"] * link["utilization"]) / 100.0, 1)

        # Drift calculation in LIVE_SYNC mode
        if self.digital_twin_mode == "LIVE_SYNC":
            self.drift_percentage = round(random.uniform(0.1, 1.4), 2)
        else:
            self.drift_percentage = round(random.uniform(5.0, 18.5), 2)

    def get_summary(self) -> Dict[str, Any]:
        total_nodes = len(self.nodes)
        active_nodes = sum(1 for n in self.nodes.values() if n["status"] == "active")
        failed_nodes = sum(1 for n in self.nodes.values() if n["status"] == "failed")
        
        total_links = len(self.links)
        active_links = sum(1 for l in self.links.values() if l["status"] == "active")
        down_links = sum(1 for l in self.links.values() if l["status"] == "down")

        avg_cpu = round(sum(n["cpu_load"] for n in self.nodes.values()) / max(1, total_nodes), 1)
        avg_latency = round(sum(l["latency"] for l in self.links.values() if l["status"] != "down") / max(1, active_links), 2) if active_links > 0 else 0.0
        total_throughput = round(sum(l["throughput"] for l in self.links.values() if l["status"] != "down"), 1)

        # Calculate network health score out of 100
        health_score = 100
        health_score -= (failed_nodes * 25)
        health_score -= (down_links * 15)
        if avg_cpu > 75:
            health_score -= 15
        health_score = max(0, min(100, health_score))

        return {
            "health_score": health_score,
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "failed_nodes": failed_nodes,
            "total_links": total_links,
            "active_links": active_links,
            "down_links": down_links,
            "avg_cpu": avg_cpu,
            "avg_latency": avg_latency,
            "total_throughput_gbps": round(total_throughput / 1000.0, 2),
            "digital_twin_mode": self.digital_twin_mode,
            "drift_percentage": self.drift_percentage,
            "active_template": self.active_template
        }
