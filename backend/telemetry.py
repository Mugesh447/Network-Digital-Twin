import random
import time
from typing import Dict, Any, List

class TelemetryEngine:
    def __init__(self, simulator):
        self.sim = simulator

    def generate_telemetry_snapshot(self) -> Dict[str, Any]:
        """
        Generates real-time SNMP/NetFlow time-series metrics for the frontend charts
        """
        return {
            "timestamp": time.time(),
            "health_score": self.sim.get_summary()["health_score"],
            "nodes_cpu": { nid: n["cpu_load"] for nid, n in self.sim.nodes.items() },
            "links_latency": { lid: l["latency"] for lid, l in self.sim.links.items() }
        }

    def analyze_ai_diagnostics(self) -> Dict[str, Any]:
        """
        Antigravity AI Copilot analysis for current network state
        """
        nodes = self.sim.nodes
        links = self.sim.links
        failed_nodes = [n for n in nodes.values() if n["status"] == "failed"]
        degraded_nodes = [n for n in nodes.values() if n["status"] == "degraded"]
        down_links = [l for l in links.values() if l["status"] == "down"]
        congested_links = [l for l in links.values() if l["status"] == "congested" or l["utilization"] > 80]

        issues = []
        recommendations = []

        for fn in failed_nodes:
            issues.append({
                "severity": "CRITICAL",
                "title": f"Device Outage: {fn['name']}",
                "description": f"Node {fn['id']} ({fn['ip']}) is completely unresponsive.",
                "affected_node": fn["id"]
            })
            recommendations.append({
                "action": "POWER_CYCLE",
                "title": f"Reboot Node {fn['name']}",
                "description": f"Trigger automated power restart sequence for device {fn['id']}.",
                "target_id": fn["id"],
                "fix_type": "heal_all"
            })

        for dl in down_links:
            issues.append({
                "severity": "HIGH",
                "title": f"Physical Link Cut: {dl['id']}",
                "description": f"Fiber cut detected between {nodes.get(dl['source'], {}).get('name', dl['source'])} and {nodes.get(dl['target'], {}).get('name', dl['target'])}.",
                "affected_link": dl["id"]
            })
            recommendations.append({
                "action": "RESTORE_LINK",
                "title": f"Solder / Re-connect Link {dl['id']}",
                "description": f"Initiate digital twin optical re-route and restore physical connectivity on link {dl['id']}.",
                "target_id": dl["id"],
                "fix_type": "heal_all"
            })

        for cl in congested_links:
            issues.append({
                "severity": "MEDIUM",
                "title": f"Bandwidth Saturation on Link {cl['id']}",
                "description": f"Utilization reached {cl['utilization']}% (Latency: {cl['latency']}ms). Potential packet queue drops.",
                "affected_link": cl["id"]
            })
            recommendations.append({
                "action": "LEAST_COST_REROUTE",
                "title": f"Dynamic OSPF Metric Adjustment",
                "description": f"Increase cost factor on link {cl['id']} to divert traffic through backup links.",
                "target_id": cl["id"],
                "fix_type": "heal_all"
            })

        if not issues:
            status_text = "Optimal Operational Condition. No SLA anomalies or physical line faults detected."
            health_status = "HEALTHY"
        elif any(i["severity"] == "CRITICAL" for i in issues):
            status_text = f"CRITICAL OUTAGE DETECTED: {len(failed_nodes)} down node(s), {len(down_links)} severed link(s)."
            health_status = "CRITICAL"
        else:
            status_text = f"DEGRADED PERFORMANCE: {len(issues)} active warning(s)."
            health_status = "DEGRADED"

        return {
            "health_status": health_status,
            "status_text": status_text,
            "issues": issues,
            "recommendations": recommendations,
            "ai_confidence": round(random.uniform(94.2, 99.1), 1)
        }
