import json
import heapq
import os
import smtplib
import sqlite3
import time
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from werkzeug.security import check_password_hash, generate_password_hash


class AdvancedOperations:
    def __init__(self, simulator, database_path: str = "telemetry_history.db"):
        self.sim = simulator
        self.database_path = database_path
        self._initialize_database()
        self.baseline_config = self._snapshot_config()

    def _snapshot_config(self) -> Dict[str, Dict[str, Any]]:
        return {
            node_id: dict(node.get("config", {}))
            for node_id, node in self.sim.nodes.items()
        }

    def get_config_drift(self) -> Dict[str, Any]:
        current = self._snapshot_config()
        changes = []
        for node_id in sorted(set(self.baseline_config) | set(current)):
            before = self.baseline_config.get(node_id, {})
            after = current.get(node_id, {})
            for key in sorted(set(before) | set(after)):
                if before.get(key) != after.get(key):
                    changes.append({
                        "node_id": node_id,
                        "field": key,
                        "baseline": before.get(key),
                        "current": after.get(key)
                    })
        node_count = len(current)
        drift_percentage = round((len({change["node_id"] for change in changes}) / max(1, node_count)) * 100, 1)
        return {
            "drift_detected": bool(changes),
            "drift_percentage": drift_percentage,
            "changed_fields": len(changes),
            "changes": changes,
            "baseline_nodes": len(self.baseline_config)
        }

    def set_config_baseline(self) -> Dict[str, Any]:
        self.baseline_config = self._snapshot_config()
        return {"success": True, "baseline_nodes": len(self.baseline_config)}

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize_database(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at REAL NOT NULL,
                    health_score REAL NOT NULL,
                    avg_cpu REAL NOT NULL,
                    avg_latency REAL NOT NULL,
                    throughput_gbps REAL NOT NULL,
                    failed_nodes INTEGER NOT NULL,
                    down_links INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )

    def record_audit(self, username: str, action: str, details: str = "") -> Dict[str, Any]:
        timestamp = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (timestamp, username, action, details) VALUES (?, ?, ?, ?)",
                (timestamp, username, action, details),
            )
        return {"timestamp": timestamp, "username": username, "action": action, "details": details}

    def audit_history(self, limit: int = 50) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT timestamp, username, action, details FROM audit_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        columns = ["timestamp", "username", "action", "details"]
        return {"events": [dict(zip(columns, row)) for row in rows]}

    def create_user(self, username: str, password: str, role: str) -> Dict[str, Any]:
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, time.time()),
                )
            except sqlite3.IntegrityError:
                return {"success": False, "error": "Username already exists"}
        return {"success": True, "username": username, "role": role}

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT username, password_hash, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row or not check_password_hash(row[1], password):
            return None
        return {"username": row[0], "role": row[2]}

    def record_telemetry(self) -> Dict[str, Any]:
        summary = self.sim.get_summary()
        captured_at = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO telemetry_history
                (captured_at, health_score, avg_cpu, avg_latency, throughput_gbps, failed_nodes, down_links)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    captured_at,
                    summary["health_score"],
                    summary["avg_cpu"],
                    summary["avg_latency"],
                    summary["total_throughput_gbps"],
                    summary["failed_nodes"],
                    summary["down_links"],
                ),
            )
        return {"success": True, "captured_at": captured_at}

    def history(self, limit: int = 60) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT captured_at, health_score, avg_cpu, avg_latency,
                       throughput_gbps, failed_nodes, down_links
                FROM telemetry_history ORDER BY captured_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        columns = ["captured_at", "health_score", "avg_cpu", "avg_latency", "throughput_gbps", "failed_nodes", "down_links"]
        return {"samples": [dict(zip(columns, row)) for row in reversed(rows)]}

    def notification_preview(self, channel: str = "teams") -> Dict[str, Any]:
        summary = self.sim.get_summary()
        status = "CRITICAL" if summary["health_score"] < 60 else "WARNING" if summary["health_score"] < 85 else "HEALTHY"
        message = {
            "title": f"Network Digital Twin: {status}",
            "text": f"Health {summary['health_score']}%, CPU {summary['avg_cpu']}%, latency {summary['avg_latency']} ms.",
            "facts": {
                "failed_nodes": summary["failed_nodes"],
                "down_links": summary["down_links"],
                "throughput_gbps": summary["total_throughput_gbps"],
            },
        }
        if channel == "email":
            return {"channel": "email", "subject": message["title"], "body": message["text"], "facts": message["facts"], "delivery": "preview"}
        return {"channel": "teams", "payload": {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": message}]}, "delivery": "preview"}

    def send_teams_webhook(self, payload: Dict[str, Any], webhook_url: Optional[str] = None) -> Dict[str, Any]:
        target = webhook_url or os.getenv("TEAMS_WEBHOOK_URL")
        if not target:
            return {"success": False, "delivery": "preview", "message": "Set TEAMS_WEBHOOK_URL to enable delivery.", "payload": payload}
        request = urllib.request.Request(target, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return {"success": 200 <= response.status < 300, "delivery": "teams_webhook", "status_code": response.status}
        except Exception as error:
            return {"success": False, "delivery": "teams_webhook", "message": str(error)}

    def send_email_alert(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Send the current health alert through configured SMTP settings."""
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        sender = os.getenv("SMTP_FROM", smtp_user or "network-digital-twin@localhost")
        target = recipient or os.getenv("ALERT_EMAIL_TO")
        if not smtp_host or not target:
            return {"success": False, "delivery": "smtp", "message": "Configure SMTP_HOST and ALERT_EMAIL_TO before sending."}

        preview = self.notification_preview("email")
        message = EmailMessage()
        message["Subject"] = preview["subject"]
        message["From"] = sender
        message["To"] = target
        message.set_content(
            f"{preview['body']}\n\n"
            f"Failed nodes: {preview['facts']['failed_nodes']}\n"
            f"Down links: {preview['facts']['down_links']}\n"
            f"Throughput: {preview['facts']['throughput_gbps']} Gbps"
        )
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as client:
                client.starttls()
                if smtp_user and smtp_password:
                    client.login(smtp_user, smtp_password)
                client.send_message(message)
            return {"success": True, "delivery": "smtp", "recipient": target}
        except Exception as error:
            return {"success": False, "delivery": "smtp", "message": str(error)}

    def gns3_sync(self) -> Dict[str, Any]:
        nodes = [{"node_id": node_id, "name": node["name"], "type": node["type"], "ip": node["ip"]} for node_id, node in self.sim.nodes.items()]
        links = [{"link_id": link_id, "source": link["source"], "target": link["target"], "status": link["status"]} for link_id, link in self.sim.links.items()]
        payload = {"nodes": nodes, "links": links}
        server_url = os.getenv("GNS3_SERVER_URL")
        project_id = os.getenv("GNS3_PROJECT_ID")
        if not server_url or not project_id:
            return {"success": True, "mode": "live_sync_ready", "delivery": "preview", "gns3_version": "2.2+", "node_count": len(nodes), "link_count": len(links), "topology": payload}

        base_url = server_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        auth_token = os.getenv("GNS3_AUTH_TOKEN")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        def push(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
            request = urllib.request.Request(f"{base_url}{path}", data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            node_map = {}
            for node in self.sim.nodes.values():
                node_type = "dynamips" if node["type"] == "router" else "ethernet_switch" if node["type"] == "switch" else "qemu"
                created = push(f"/v2/projects/{project_id}/nodes", {
                    "name": node["name"],
                    "node_type": node_type,
                    "compute_id": "local",
                    "x": node["x"],
                    "y": node["y"],
                    "properties": {"platform": "c7200" if node["type"] == "router" else "c3725"}
                })
                node_map[node["id"]] = created["node_id"]

            for link in self.sim.links.values():
                push(f"/v2/projects/{project_id}/links", {
                    "nodes": [
                        {"node_id": node_map[link["source"]], "adapter_number": 0, "port_number": 0},
                        {"node_id": node_map[link["target"]], "adapter_number": 0, "port_number": 1}
                    ],
                    "suspend": link["status"] == "down"
                })
            return {"success": True, "mode": "live_sync", "delivery": "gns3_api", "project_id": project_id, "node_count": len(nodes), "link_count": len(links)}
        except Exception as error:
            return {"success": False, "mode": "live_sync", "delivery": "gns3_api", "message": str(error), "created_nodes": len(node_map)}

    def forecast_failures(self) -> Dict[str, Any]:
        """Estimate near-term risk from current telemetry thresholds."""
        predictions = []
        for node in self.sim.nodes.values():
            risk_score = 0
            signals = []
            if node["status"] == "failed":
                risk_score = 100
                signals.append("device is already failed")
            elif node["status"] == "degraded":
                risk_score += 45
                signals.append("device is degraded")
            if node["cpu_load"] >= 80:
                risk_score += 35
                signals.append(f"CPU {node['cpu_load']}%")
            elif node["cpu_load"] >= 65:
                risk_score += 15
                signals.append(f"elevated CPU {node['cpu_load']}%")
            if node["ram_load"] >= 80:
                risk_score += 25
                signals.append(f"RAM {node['ram_load']}%")
            if risk_score >= 20:
                predictions.append({
                    "target_id": node["id"],
                    "target_name": node["name"],
                    "asset_type": "node",
                    "risk_score": min(100, risk_score),
                    "horizon": "next 15 minutes",
                    "signals": signals,
                    "action": "Reduce load or fail over traffic."
                })

        for link in self.sim.links.values():
            risk_score = 0
            signals = []
            if link["status"] == "down":
                risk_score = 100
                signals.append("link is down")
            if link["utilization"] >= 80:
                risk_score += 40
                signals.append(f"utilization {link['utilization']}%")
            if link["latency"] >= 50:
                risk_score += 30
                signals.append(f"latency {link['latency']} ms")
            if link["loss"] >= 5:
                risk_score += 30
                signals.append(f"packet loss {link['loss']}%")
            if risk_score >= 20:
                predictions.append({
                    "target_id": link["id"],
                    "target_name": f"{link['source']} <-> {link['target']}",
                    "asset_type": "link",
                    "risk_score": min(100, risk_score),
                    "horizon": "next 15 minutes",
                    "signals": signals,
                    "action": "Reroute traffic or increase link capacity."
                })

        predictions.sort(key=lambda item: item["risk_score"], reverse=True)
        return {
            "model": "threshold-risk-v1",
            "confidence": 0.82 if predictions else 0.94,
            "predictions": predictions[:10],
            "sampled_at": time.time()
        }

    def optimize_route(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """Find a route that actively avoids congested links."""
        if source_id not in self.sim.nodes or target_id not in self.sim.nodes:
            return {"success": False, "reason": "Invalid source or target node", "path_nodes": [], "path_links": []}
        if self.sim.nodes[source_id]["status"] == "failed" or self.sim.nodes[target_id]["status"] == "failed":
            return {"success": False, "reason": "Source or target node is down", "path_nodes": [], "path_links": []}

        adjacency = {node_id: [] for node_id in self.sim.nodes}
        for link in self.sim.links.values():
            if link["status"] == "down":
                continue
            cost = (
                link["latency"] * (1 + link["loss"] / 10.0)
                + 100.0 / max(1, link["bandwidth"])
                + (link["utilization"] / 100.0) * 4.0
            )
            edge = (link["source"], link["target"], cost, link)
            reverse = (link["target"], link["source"], cost, link)
            adjacency[link["source"]].append(edge)
            adjacency[link["target"]].append(reverse)

        distances = {node_id: float("inf") for node_id in self.sim.nodes}
        previous = {node_id: None for node_id in self.sim.nodes}
        edge_used = {node_id: None for node_id in self.sim.nodes}
        distances[source_id] = 0
        queue = [(0, source_id)]
        while queue:
            distance, current = heapq.heappop(queue)
            if distance > distances[current]:
                continue
            if current == target_id:
                break
            for neighbor, _, cost, link in adjacency[current]:
                if self.sim.nodes[neighbor]["status"] == "failed":
                    continue
                candidate = distance + cost
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    previous[neighbor] = current
                    edge_used[neighbor] = link
                    heapq.heappush(queue, (candidate, neighbor))

        if distances[target_id] == float("inf"):
            return {"success": False, "reason": "No healthy route available", "path_nodes": [], "path_links": []}

        path_nodes = []
        path_links = []
        total_latency = 0.0
        current = target_id
        while current is not None:
            path_nodes.append(current)
            link = edge_used[current]
            if link:
                path_links.append(link["id"])
                total_latency += link["latency"]
            current = previous[current]
        path_nodes.reverse()
        path_links.reverse()
        max_utilization = max([self.sim.links[link_id]["utilization"] for link_id in path_links] or [0])
        baseline = self.sim.find_path(source_id, target_id)
        return {
            "success": True,
            "path_nodes": path_nodes,
            "path_links": path_links,
            "hop_count": len(path_nodes) - 1,
            "total_latency_ms": round(total_latency, 2),
            "max_path_utilization": max_utilization,
            "rerouted": baseline.get("path_links") != path_links,
            "optimization": "latency + packet loss + bandwidth + utilization"
        }

    def capacity_plan(self, growth_percent: float = 25.0, horizon_months: int = 6) -> Dict[str, Any]:
        growth = max(0.0, min(float(growth_percent), 500.0)) / 100.0
        horizon = max(1, min(int(horizon_months), 60))
        monthly_factor = (1 + growth) ** (horizon / 12.0)
        links: List[Dict[str, Any]] = []
        for link in self.sim.links.values():
            projected = link["throughput"] * monthly_factor
            capacity = link["bandwidth"]
            links.append({
                "link_id": link["id"],
                "current_mbps": link["throughput"],
                "projected_mbps": round(projected, 1),
                "capacity_mbps": capacity,
                "projected_utilization": round(projected / max(1, capacity) * 100, 1),
                "action": "Upgrade capacity" if projected / max(1, capacity) >= 0.8 else "Monitor"
            })
        links.sort(key=lambda item: item["projected_utilization"], reverse=True)
        return {"growth_percent": growth_percent, "horizon_months": horizon, "links": links, "upgrade_count": sum(item["action"] == "Upgrade capacity" for item in links)}
