from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from simulator import NetworkSimulator
from gns3_tracer_converter import TopologyConverter
from telemetry import TelemetryEngine
import os
import time

app = Flask(__name__, static_folder="static")
CORS(app)

sim = NetworkSimulator()
telemetry_engine = TelemetryEngine(sim)

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/topology", methods=["GET"])
def get_topology():
    sim.tick_telemetry()
    return jsonify({
        "nodes": list(sim.nodes.values()),
        "links": list(sim.links.values()),
        "summary": sim.get_summary(),
        "incidents": sim.incidents_log[:30]
    })

@app.route("/api/topology/template", methods=["POST"])
def load_template():
    data = request.json or {}
    template_name = data.get("template", "enterprise_campus")
    sim.load_template(template_name)
    return jsonify({"success": True, "summary": sim.get_summary()})

@app.route("/api/topology/node", methods=["POST"])
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
def inject_failure():
    data = request.json or {}
    failure_type = data.get("type")
    target_id = data.get("target_id")
    intensity = float(data.get("intensity", 1.0))

    res = sim.inject_failure(failure_type, target_id, intensity)
    return jsonify(res)

@app.route("/api/simulate/heal", methods=["POST"])
def heal_network():
    res = sim.heal_all()
    return jsonify(res)

@app.route("/api/simulate/path", methods=["POST"])
def calculate_path():
    data = request.json or {}
    source = data.get("source")
    target = data.get("target")
    res = sim.find_path(source, target)
    return jsonify(res)

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    sim.tick_telemetry()
    return jsonify({
        "summary": sim.get_summary(),
        "nodes": [{ "id": n["id"], "name": n["name"], "cpu": n["cpu_load"], "ram": n["ram_load"], "status": n["status"] } for n in sim.nodes.values()],
        "links": [{ "id": l["id"], "utilization": l["utilization"], "throughput": l["throughput"], "latency": l["latency"], "status": l["status"] } for l in sim.links.values()]
    })

@app.route("/api/ai/diagnostics", methods=["GET"])
def get_ai_diagnostics():
    res = telemetry_engine.analyze_ai_diagnostics()
    return jsonify(res)

@app.route("/api/export/gns3", methods=["GET"])
def export_gns3():
    data = TopologyConverter.export_gns3(sim.nodes, sim.links)
    return jsonify(data)

@app.route("/api/export/packet_tracer", methods=["GET"])
def export_packet_tracer():
    data = TopologyConverter.export_packet_tracer(sim.nodes, sim.links)
    return jsonify(data)

@app.route("/api/export/cisco_config", methods=["POST"])
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
def set_twin_mode():
    data = request.json or {}
    mode = data.get("mode", "LIVE_SYNC")
    if mode in ["LIVE_SYNC", "ISOLATED_SANDBOX"]:
        sim.digital_twin_mode = mode
        sim.log_incident("INFO", f"DIGITAL TWIN MODE: Switched to '{mode}' mode.")
        return jsonify({"success": True, "mode": mode})
    return jsonify({"success": False, "error": "Invalid mode"}), 400

@app.route("/api/cli/execute", methods=["POST"])
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
