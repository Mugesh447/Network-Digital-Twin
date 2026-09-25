from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from simulator import NetworkSimulator
from gns3_tracer_converter import TopologyConverter
from telemetry import TelemetryEngine
from advanced_features import AdvancedOperations
from werkzeug.exceptions import BadRequest
from functools import wraps
import json
import os
from pathlib import Path
import secrets
import time

try:
    from flask_sock import Sock
except ImportError:
    Sock = None

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "frontend"))
CORS(app)

sim = NetworkSimulator()
telemetry_engine = TelemetryEngine(sim)
advanced_operations = AdvancedOperations(sim)
socket_server = Sock(app) if Sock else None
ROLE_PERMISSIONS = {
    "admin": ["view", "simulate", "configure", "export"],
    "operator": ["view", "simulate", "export"],
    "viewer": ["view"]
}
DEMO_USERS = {"admin": "admin123", "operator": "operator123", "viewer": "viewer123"}
active_sessions = {}


def session_for_request():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ") or request.cookies.get("ndt_session")
    return active_sessions.get(token)


def require_permission(permission):
    def decorator(handler):
        @wraps(handler)
        def guarded(*args, **kwargs):
            session = session_for_request()
            if not session:
                return jsonify({"success": False, "error": "Authentication required"}), 401
            if permission not in ROLE_PERMISSIONS.get(session["role"], []):
                return jsonify({"success": False, "error": f"Role '{session['role']}' cannot perform '{permission}'"}), 403
            return handler(*args, **kwargs)
        return guarded
    return decorator


def session_response(payload, token, status=200):
    response = jsonify(payload)
    response.set_cookie("ndt_session", token, httponly=True, samesite="Lax", max_age=86400)
    response.status_code = status
    return response


def record_audit(action, details=""):
    session = session_for_request()
    username = session["username"] if session else "system"
    return advanced_operations.record_audit(username, action, details)


def telemetry_payload():
    return {
        "type": "telemetry",
        "summary": sim.get_summary(),
        "nodes": list(sim.nodes.values()),
        "links": list(sim.links.values()),
        "incidents": sim.incidents_log[:30],
        "ai_diagnostics": telemetry_engine.analyze_ai_diagnostics()
    }


if socket_server:
    @socket_server.route("/ws/telemetry")
    def telemetry_socket(ws):
        while True:
            sim.tick_telemetry()
            advanced_operations.record_telemetry()
            ws.send(json.dumps(telemetry_payload()))
            time.sleep(2)

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "")
    if username in DEMO_USERS:
        if DEMO_USERS[username] != data.get("password"):
            return jsonify({"success": False, "error": "Invalid username or password"}), 401
        role = username if username in ROLE_PERMISSIONS else "viewer"
    else:
        stored_user = advanced_operations.authenticate_user(username, data.get("password", ""))
        if not stored_user:
            return jsonify({"success": False, "error": "Invalid username or password"}), 401
        role = stored_user["role"]
    token = secrets.token_urlsafe(24)
    active_sessions[token] = {"username": username, "role": role}
    return session_response({"success": True, "token": token, "username": username, "role": role, "permissions": ROLE_PERMISSIONS[role]}, token)

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))
    role = data.get("role", "viewer")
    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "error": "Username must be 3+ characters and password 6+ characters"}), 400
    if username in DEMO_USERS:
        return jsonify({"success": False, "error": "Username already exists"}), 409
    if role not in ["operator", "viewer"]:
        return jsonify({"success": False, "error": "New accounts can only be viewer or operator"}), 400
    created = advanced_operations.create_user(username, password, role)
    if not created["success"]:
        return jsonify(created), 409
    token = secrets.token_urlsafe(24)
    active_sessions[token] = {"username": username, "role": role}
    return session_response({"success": True, "token": token, "username": username, "role": role, "permissions": ROLE_PERMISSIONS[role]}, token)

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ") or request.cookies.get("ndt_session")
    active_sessions.pop(token, None)
    response = jsonify({"success": True})
    response.delete_cookie("ndt_session")
    return response

@app.route("/api/auth/session", methods=["GET"])
def auth_session():
    session = session_for_request()
    if not session:
        return jsonify({"authenticated": False, "role": "viewer", "permissions": ROLE_PERMISSIONS["viewer"]})
    return jsonify({"authenticated": True, **session, "permissions": ROLE_PERMISSIONS[session["role"]]})

@app.route("/api/auth/role", methods=["POST"])
def change_role():
    session = session_for_request()
    role = (request.json or {}).get("role")
    if not session or session["role"] != "admin":
        return jsonify({"success": False, "error": "Admin session required"}), 403
    if role not in ROLE_PERMISSIONS:
        return jsonify({"success": False, "error": "Unsupported role"}), 400
    session["role"] = role
    return jsonify({"success": True, "role": role, "permissions": ROLE_PERMISSIONS[role]})

@app.route("/api/topology", methods=["GET"])
@require_permission("view")
def get_topology():
    sim.tick_telemetry()
    return jsonify({
        "nodes": list(sim.nodes.values()),
        "links": list(sim.links.values()),
        "summary": sim.get_summary(),
        "incidents": sim.incidents_log[:30]
    })

@app.route("/topology", methods=["GET"])
@require_permission("view")
def get_topology_compat():
    return get_topology()

@app.route("/api/topology/save", methods=["GET"])
@app.route("/topology/save", methods=["GET"])
@require_permission("export")
def save_topology():
    return jsonify(sim.export_topology())

@app.route("/api/topology/load", methods=["POST"])
@app.route("/topology/load", methods=["POST"])
@require_permission("configure")
def load_topology():
    try:
        result = sim.import_topology(request.get_json(silent=True) or {})
        return jsonify({"success": True, **result})
    except ValueError as error:
        raise BadRequest(str(error))

@app.route("/api/topology/template", methods=["POST"])
@require_permission("configure")
def load_template():
    data = request.json or {}
    template_name = data.get("template", "enterprise_campus")
    sim.load_template(template_name)
    return jsonify({"success": True, "summary": sim.get_summary()})

@app.route("/api/topology/node", methods=["POST"])
@require_permission("configure")
def add_node():
    data = request.json or {}
    node_id = data.get("id", f"node_{int(time.time())}")
    name = data.get("name", "New Device")
    node_type = data.get("type", "router")
    ip = data.get("ip", "10.0.0.99")
    x = data.get("x", 400)
    y = data.get("y", 300)

    sim.add_node(node_id, name, node_type, ip, x, y)
    return jsonify({"success": True, "node_id": node_id})

@app.route("/api/topology/node/position", methods=["POST"])
@require_permission("configure")
def update_node_position():
    data = request.json or {}
    node_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    if node_id in sim.nodes and x is not None and y is not None:
        sim.nodes[node_id]["x"] = x
        sim.nodes[node_id]["y"] = y
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid node or coordinates"}), 400

@app.route("/api/topology/link", methods=["POST"])
@require_permission("configure")
def add_link():
    data = request.json or {}
    link_id = data.get("id", f"link_{int(time.time())}")
    source = data.get("source")
    target = data.get("target")
    bw = int(data.get("bandwidth", 1000))
    lat = float(data.get("latency", 2.0))

    if source in sim.nodes and target in sim.nodes:
        sim.add_link(link_id, source, target, bw, lat)
        return jsonify({"success": True, "link_id": link_id})
    return jsonify({"success": False, "error": "Source or Target node not found"}), 400

@app.route("/api/simulate/failure", methods=["POST"])
@require_permission("simulate")
def inject_failure():
    data = request.json or {}
    failure_type = data.get("type")
    target_id = data.get("target_id")
    intensity = float(data.get("intensity", 1.0))

    res = sim.inject_failure(failure_type, target_id, intensity)
    record_audit("failure_simulation", f"type={failure_type}; target={target_id}; intensity={intensity}")
    return jsonify(res)

@app.route("/api/simulate/heal", methods=["POST"])
@require_permission("simulate")
def heal_network():
    res = sim.heal_all()
    record_audit("network_heal", "restored all nodes and links")
    return jsonify(res)

@app.route("/api/simulate/path", methods=["POST"])
@require_permission("view")
def calculate_path():
    data = request.json or {}
    source = data.get("source")
    target = data.get("target")
    res = sim.find_path(source, target)
    return jsonify(res)

@app.route("/api/simulate/connectivity", methods=["POST"])
@require_permission("view")
def calculate_connectivity():
    data = request.json or {}
    return jsonify(sim.bfs_connectivity(data.get("source"), data.get("target")))

@app.route("/api/telemetry", methods=["GET"])
@require_permission("view")
def get_telemetry():
    sim.tick_telemetry()
    advanced_operations.record_telemetry()
    return jsonify({
        "summary": sim.get_summary(),
        "nodes": [{ "id": n["id"], "name": n["name"], "cpu": n["cpu_load"], "ram": n["ram_load"], "status": n["status"] } for n in sim.nodes.values()],
        "links": [{ "id": l["id"], "utilization": l["utilization"], "throughput": l["throughput"], "latency": l["latency"], "status": l["status"] } for l in sim.links.values()]
    })

@app.route("/health", methods=["GET"])
def health_check():
    summary = sim.get_summary()
    return jsonify({"status": "ok", "health_score": summary["health_score"], "nodes": summary["total_nodes"], "links": summary["total_links"]})

@app.route("/metrics", methods=["GET"])
def metrics():
    summary = sim.get_summary()
    lines = [
        "# HELP network_health_score Current network health score.",
        "# TYPE network_health_score gauge",
        f"network_health_score {summary['health_score']}",
        "# HELP network_active_nodes Number of active nodes.",
        "# TYPE network_active_nodes gauge",
        f"network_active_nodes {summary['active_nodes']}",
        "# HELP network_active_links Number of active links.",
        "# TYPE network_active_links gauge",
        f"network_active_links {summary['active_links']}",
        "# HELP network_avg_latency_ms Average link latency in milliseconds.",
        "# TYPE network_avg_latency_ms gauge",
        f"network_avg_latency_ms {summary['avg_latency']}",
    ]
    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}

@app.route("/api/ai/diagnostics", methods=["GET"])
@require_permission("view")
def get_ai_diagnostics():
    res = telemetry_engine.analyze_ai_diagnostics()
    return jsonify(res)

@app.route("/api/insights", methods=["GET"])
@require_permission("view")
def get_network_insights():
    return jsonify(telemetry_engine.generate_network_insights())

@app.route("/api/advanced/forecast", methods=["GET"])
@require_permission("view")
def get_failure_forecast():
    return jsonify(advanced_operations.forecast_failures())

@app.route("/api/advanced/route-optimize", methods=["POST"])
@require_permission("optimize")
def optimize_route():
    data = request.json or {}
    return jsonify(advanced_operations.optimize_route(data.get("source"), data.get("target")))

@app.route("/api/history", methods=["GET"])
@require_permission("view")
def get_telemetry_history():
    return jsonify(advanced_operations.history(request.args.get("limit", 60)))

@app.route("/api/alerts/preview", methods=["POST"])
@require_permission("view")
def preview_alert():
    data = request.json or {}
    return jsonify(advanced_operations.notification_preview(data.get("channel", "teams")))

@app.route("/api/alerts/teams", methods=["POST"])
@require_permission("configure")
def send_teams_alert():
    data = request.json or {}
    payload = data.get("payload") or advanced_operations.notification_preview("teams")["payload"]
    result = advanced_operations.send_teams_webhook(payload, data.get("webhook_url"))
    record_audit("teams_alert", f"delivery={result.get('delivery')}; success={result.get('success')}")
    return jsonify(result)

@app.route("/api/alerts/email", methods=["POST"])
@require_permission("configure")
def send_email_alert():
    data = request.json or {}
    result = advanced_operations.send_email_alert(data.get("recipient"))
    record_audit("email_alert", f"delivery={result.get('delivery')}; success={result.get('success')}")
    return jsonify(result)

@app.route("/api/gns3/sync", methods=["POST"])
@require_permission("export")
def sync_gns3():
    return jsonify(advanced_operations.gns3_sync())

@app.route("/api/capacity-plan", methods=["POST"])
@require_permission("view")
def get_capacity_plan():
    data = request.json or {}
    return jsonify(advanced_operations.capacity_plan(data.get("growth_percent", 25), data.get("horizon_months", 6)))

@app.route("/api/config-drift", methods=["GET"])
@require_permission("view")
def get_config_drift():
    return jsonify(advanced_operations.get_config_drift())

@app.route("/api/config-drift/baseline", methods=["POST"])
@require_permission("configure")
def set_config_baseline():
    result = advanced_operations.set_config_baseline()
    record_audit("configuration_baseline_changed", f"baseline_nodes={result['baseline_nodes']}")
    return jsonify(result)

@app.route("/api/audit-log", methods=["GET"])
@require_permission("view")
def get_audit_log():
    return jsonify(advanced_operations.audit_history(request.args.get("limit", 50)))

@app.route("/api/export/gns3", methods=["GET"])
@require_permission("export")
def export_gns3():
    data = TopologyConverter.export_gns3(sim.nodes, sim.links)
    return jsonify(data)

@app.route("/api/export/packet_tracer", methods=["GET"])
@require_permission("export")
def export_packet_tracer():
    data = TopologyConverter.export_packet_tracer(sim.nodes, sim.links)
    return jsonify(data)

@app.route("/api/export/cisco_config", methods=["POST"])
@require_permission("configure")
def export_cisco_config():
    data = request.json or {}
    node_id = data.get("node_id")
    if node_id in sim.nodes:
        node = sim.nodes[node_id]
        neighbors = []
        for lid, link in sim.links.items():
            if link["source"] == node_id and link["target"] in sim.nodes:
                neighbors.append(sim.nodes[link["target"]])
            elif link["target"] == node_id and link["source"] in sim.nodes:
                neighbors.append(sim.nodes[link["source"]])
        
        cli_config = TopologyConverter.generate_cisco_ios_config(node, neighbors)
        return jsonify({"success": True, "node_id": node_id, "config": cli_config})
    return jsonify({"success": False, "error": "Node not found"}), 404

@app.route("/api/twin/mode", methods=["POST"])
@require_permission("configure")
def set_twin_mode():
    data = request.json or {}
    mode = data.get("mode", "LIVE_SYNC")
    if mode in ["LIVE_SYNC", "ISOLATED_SANDBOX"]:
        sim.digital_twin_mode = mode
        sim.log_incident("INFO", f"DIGITAL TWIN MODE: Switched to '{mode}' mode.")
        return jsonify({"success": True, "mode": mode})
    return jsonify({"success": False, "error": "Invalid mode"}), 400

@app.route("/api/cli/execute", methods=["POST"])
@require_permission("view")
def execute_cli_command():
    data = request.json or {}
    node_id = data.get("node_id")
    command = data.get("command", "").strip().lower()

    if node_id not in sim.nodes:
        return jsonify({"output": "Error: Node context not selected or device down."})

    node = sim.nodes[node_id]
    
    if node["status"] == "failed":
        return jsonify({"output": "% Device is unpowered or unreachable."})

    if command == "show ip route":
        output = [f"Codes: C - connected, S - static, R - RIP, M - mobile, B - BGP, O - OSPF", ""]
        output.append(f"Gateway of last resort is 10.0.0.1 to network 0.0.0.0\n")
        output.append(f"C    127.0.0.0/8 is directly connected, Loopback0")
        output.append(f"C    {node['ip']}/32 is directly connected, GigabitEthernet0/0")
        for route in node.get("routing_table", []):
            output.append(f"O    {route['destination']} [{route['metric']}] via {route['next_hop']}, 00:14:22, GigabitEthernet0/1")
        return jsonify({"output": "\n".join(output)})

    elif command in ["show interfaces", "show int"]:
        lines = []
        for iface in node["interfaces"]:
            lines.append(f"{iface['name']} is {iface['status'].upper()}, line protocol is UP")
            lines.append(f"  Hardware is GigabitEthernet, address is 5254.0012.3456")
            lines.append(f"  Internet address is {iface['ip']}/24")
            lines.append(f"  MTU 1500 bytes, BW {iface['speed']}, DLY 10 usec, reliability 255/255, txload 1/255, rxload 1/255")
            lines.append(f"  5 minute input rate 142000 bits/sec, 45 packets/sec")
            lines.append(f"  5 minute output rate 98000 bits/sec, 31 packets/sec")
            lines.append(f"")
        return jsonify({"output": "\n".join(lines)})

    elif command.startswith("ping"):
        parts = command.split()
        target = parts[1] if len(parts) > 1 else "8.8.8.8"
        target_node_id = None
        for nid, n in sim.nodes.items():
            if n["ip"] == target or n["name"].lower() == target.lower() or nid == target:
                target_node_id = nid
                break
        
        if target_node_id:
            path_res = sim.find_path(node_id, target_node_id)
            if path_res["success"]:
                rtt = path_res["total_latency_ms"]
                out = f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n!!!!!\nSuccess rate is 100 percent (5/5), round-trip min/avg/max = {round(rtt*0.8, 1)}/{rtt}/{round(rtt*1.2, 1)} ms"
            else:
                out = f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n.....\nSuccess rate is 0 percent (0/5) - {path_res.get('reason', 'Unreachable')}"
        else:
            out = f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n!!!!!\nSuccess rate is 100 percent (5/5), round-trip min/avg/max = 1.2/2.4/4.1 ms"

        return jsonify({"output": out})

    elif command.startswith("traceroute") or command.startswith("trace"):
        parts = command.split()
        target = parts[1] if len(parts) > 1 else "8.8.8.8"
        target_node_id = None
        for nid, n in sim.nodes.items():
            if n["ip"] == target or n["name"].lower() == target.lower() or nid == target:
                target_node_id = nid
                break
        
        if target_node_id:
            path_res = sim.find_path(node_id, target_node_id)
            if path_res["success"]:
                lines = [f"Tracing the route to {target}"]
                for idx, hop_id in enumerate(path_res["path_nodes"]):
                    hop_node = sim.nodes[hop_id]
                    lines.append(f"  {idx + 1}  {hop_node['ip']} ({hop_node['name']})  {round((idx+1)*1.5, 1)} msec  {round((idx+1)*1.6, 1)} msec")
                out = "\n".join(lines)
            else:
                out = f"Tracing the route to {target}\n  1  * * *\n  2  * * *\n  Destination unreachable."
        else:
            out = f"Tracing the route to {target}\n  1  10.0.0.1 1.2 msec 1.1 msec\n  2  {target} 4.3 msec 4.1 msec"

        return jsonify({"output": out})

    elif command in ["show version", "sh ver"]:
        out = (
            f"Cisco IOS Software, C7200 Software (C7200-ADVENTERPRISEK9-M), Version 15.4(3)S5, RELEASE SOFTWARE\n"
            f"Technical Support: http://www.cisco.com/techsupport\n"
            f"Compiled Sun 20-Jul-26 14:10 by net-digital-twin\n\n"
            f"System uptime is 14 weeks, 2 days, 8 hours, 12 minutes\n"
            f"System restarted by power-on\n"
            f"cisco 7206VXR (NPE400) processor with 491520K/32768K bytes of memory.\n"
            f"Processor board ID 28374921\n"
            f"R7000 CPU at 350MHz, Implementation 39, Rev 2.1, 256KB L2 Cache\n"
            f"6 Gigabit Ethernet interfaces\n"
            f"512K bytes of NVRAM.\n"
        )
        return jsonify({"output": out})

    elif command == "shutdown":
        sim.inject_failure("crash_node", node_id)
        return jsonify({"output": f"% Interface GigabitEthernet0/0, changed state to administratively down\n% Node {node['name']} powered off."})

    elif command in ["no shutdown", "no shut"]:
        sim.nodes[node_id]["status"] = "active"
        sim.update_routing_tables()
        return jsonify({"output": f"% Interface GigabitEthernet0/0, changed state to up\n% Node {node['name']} operational."})

    elif command == "help":
        return jsonify({"output": "Supported Commands:\n - show ip route\n - show interfaces\n - ping <target_ip>\n - traceroute <target_ip>\n - show version\n - shutdown\n - no shutdown"})

    else:
        return jsonify({"output": f"% Invalid command or syntax error at '{command}'. Type 'help' for available commands."})

if __name__ == "__main__":
    print("Network Digital Twin Server starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
