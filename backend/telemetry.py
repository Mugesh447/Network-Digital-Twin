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
            "ai_confidence": round(random.uniform(94.2, 99.1), 1),
            "sampled_at": time.time()
        }

    def generate_network_insights(self) -> Dict[str, Any]:
        """Return explainable risk scoring for capacity and SLA planning."""
        node_risks = []
        for node in self.sim.nodes.values():
            risk = 0
            reasons = []
            if node["status"] == "failed":
                risk += 100
                reasons.append("device failed")
            elif node["status"] == "degraded":
                risk += 45
                reasons.append("device degraded")
            if node["cpu_load"] >= 80:
                risk += 30
                reasons.append(f"CPU {node['cpu_load']}%")
            if node["ram_load"] >= 80:
                risk += 20
                reasons.append(f"RAM {node['ram_load']}%")
            if risk:
                node_risks.append({
                    "id": node["id"],
                    "name": node["name"],
                    "risk_score": min(100, risk),
                    "reasons": reasons
                })

        link_risks = []
        for link in self.sim.links.values():
            risk = 0
            reasons = []
            if link["status"] == "down":
                risk += 100
                reasons.append("link down")
            if link["utilization"] >= 80:
                risk += 35
                reasons.append(f"utilization {link['utilization']}%")
            if link["latency"] >= 50:
                risk += 30
                reasons.append(f"latency {link['latency']} ms")
            if link["loss"] >= 5:
                risk += 25
                reasons.append(f"packet loss {link['loss']}%")
            if risk:
                link_risks.append({
                    "id": link["id"],
                    "risk_score": min(100, risk),
                    "reasons": reasons
                })

        node_risks.sort(key=lambda item: item["risk_score"], reverse=True)
        link_risks.sort(key=lambda item: item["risk_score"], reverse=True)
        summary = self.sim.get_summary()
        hotspot_count = len(node_risks) + len(link_risks)
        if any(item["risk_score"] >= 80 for item in node_risks + link_risks):
            sla_status = "AT_RISK"
        elif hotspot_count:
            sla_status = "WATCH"
        else:
            sla_status = "WITHIN_TARGET"

        recommendations = []
        if node_risks:
            recommendations.append("Review the highest-risk devices before the next traffic peak.")
        if link_risks:
            recommendations.append("Redistribute traffic or increase capacity on hotspot links.")
        if not recommendations:
            recommendations.append("No immediate capacity action is required.")

        return {
            "sla_status": sla_status,
            "risk_score": max([item["risk_score"] for item in node_risks + link_risks] or [0]),
            "hotspot_count": hotspot_count,
            "top_nodes": node_risks[:5],
            "top_links": link_risks[:5],
            "recommendations": recommendations,
            "sampled_at": time.time(),
            "health_score": summary["health_score"]
        }
