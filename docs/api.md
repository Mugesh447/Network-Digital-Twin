# Network Digital Twin API

Base URL: `http://localhost:5000`

The browser receives an HTTP-only `ndt_session` cookie after login or account creation. Protected requests use that cookie automatically. A bearer token is also accepted:

```http
Authorization: Bearer <token>
```

## Permission Matrix

| Permission | Viewer | Operator | Admin |
|---|---:|---:|---:|
| `view` | Yes | Yes | Yes |
| `simulate` | No | Yes | Yes |
| `optimize` | No | Yes | Yes |
| `export` | No | Yes | Yes |
| `configure` | No | No | Yes |

Unauthorized requests return `401`. Authenticated users without the required permission return `403`.

## Authentication

### `POST /api/auth/login`

Permission: public.

Request:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

Response:

```json
{
  "success": true,
  "token": "session-token",
  "username": "admin",
  "role": "admin",
  "permissions": ["view", "simulate", "configure", "export"]
}
```

### `POST /api/auth/register`

Permission: public. New accounts can use `viewer` or `operator` roles.

Request:

```json
{
  "username": "network_user",
  "password": "secure-password",
  "role": "viewer"
}
```

Response: same session response as login. Accounts are stored in SQLite with password hashes.

### `GET /api/auth/session`

Permission: public.

Response:

```json
{
  "authenticated": true,
  "username": "admin",
  "role": "admin",
  "permissions": ["view", "simulate", "configure", "export"]
}
```

### `POST /api/auth/logout`

Permission: public. Clears the session cookie.

### `POST /api/auth/role`

Permission: admin session required.

Request:

```json
{"role": "operator"}
```

Response:

```json
{"success": true, "role": "operator", "permissions": ["view", "simulate", "optimize", "export"]}
```

## Health and Realtime

### `GET /health`

Permission: public.

Response:

```json
{"status": "ok", "health_score": 100, "nodes": 12, "links": 14}
```

### `GET /metrics`

Permission: public. Returns Prometheus-compatible text metrics for health, active nodes, active links, and average latency.

### `WebSocket /ws/telemetry`

Permission: authenticated session. Pushes topology, node/link telemetry, incidents, summary, and AI diagnostics every two seconds.

## Topology

### `GET /api/topology`

Permission: `view`.

Response includes `nodes`, `links`, `summary`, and `incidents`.

### `GET /api/topology/save`

Permission: `export`.

Response includes the current topology JSON with `active_template`, `digital_twin_mode`, `nodes`, and `links`.

### `POST /api/topology/load`

Permission: `configure`.

Request: topology JSON from `/api/topology/save`.

Response:

```json
{"success": true, "nodes": 12, "links": 14}
```

### `POST /api/topology/template`

Permission: `configure`.

Request:

```json
{"template": "enterprise_campus"}
```

Supported templates include `enterprise_campus`, `spine_leaf_datacenter`, and `isp_backbone`.

### `POST /api/topology/node`

Permission: `configure`.

Request:

```json
{"id": "r9", "name": "Branch Gateway", "type": "router", "ip": "10.0.0.9", "x": 400, "y": 300}
```

Response: `{"success": true, "node_id": "r9"}`.

### `POST /api/topology/link`

Permission: `configure`.

Request:

```json
{"id": "l9", "source": "r1", "target": "r2", "bandwidth": 1000, "latency": 2}
```

Response: `{"success": true, "link_id": "l9"}`.

## Simulation and Routing

### `POST /api/simulate/failure`

Permission: `simulate`.

Request:

```json
{"type": "ddos_attack", "target_id": "r1", "intensity": 1.0}
```

Failure types: `cut_link`, `crash_node`, `inject_latency`, `packet_loss`, `ddos_attack`.

Response: `{"success": true, "message": "..."}`.

### `POST /api/simulate/heal`

Permission: `simulate`.

Response: `{"success": true, "message": "All network elements restored..."}`.

### `POST /api/simulate/path`

Permission: `view`.

Request:

```json
{"source": "r1", "target": "srv2"}
```

Response contains `path_nodes`, `path_links`, `total_latency_ms`, `estimated_loss_percent`, and `hop_count`.

### `POST /api/simulate/connectivity`

Permission: `view`. Uses BFS reachability.

Response:

```json
{"reachable": true, "path": ["r1", "r2", "srv2"], "hop_count": 2}
```

### `POST /api/advanced/route-optimize`

Permission: `optimize`.

Request: source and target node IDs.

Response includes the congestion-aware route, `max_path_utilization`, `rerouted`, and the optimization cost model.

## Telemetry and AI

### `GET /api/telemetry`

Permission: `view`.

Response includes summary, node CPU/RAM/status, and link utilization/throughput/latency/status.

### `GET /api/ai/diagnostics`

Permission: `view`.

Response includes `health_status`, `status_text`, `issues`, `recommendations`, `ai_confidence`, and `sampled_at`.

### `GET /api/advanced/forecast`

Permission: `view`.

Response includes threshold-based near-term predictions with target, risk score, signals, horizon, and recommended action.

### `GET /api/insights`

Permission: `view`.

Response includes SLA status, risk score, node/link hotspots, and recommendations.

### `GET /api/history?limit=60`

Permission: `view`. Returns stored SQLite telemetry samples.

### `GET /api/audit-log?limit=50`

Permission: `view`.

Response:

```json
{
  "events": [
    {
      "timestamp": 1790344000.12,
      "username": "admin",
      "action": "failure_simulation",
      "details": "type=ddos_attack; target=r1; intensity=1.0"
    }
  ]
}
```

Audit actions include failure simulation, network heal, configuration baseline changes, email alerts, and Teams alerts.

### `POST /api/capacity-plan`

Permission: `view`.

Request:

```json
{"growth_percent": 25, "horizon_months": 6}
```

Response includes projected utilization for each link and `upgrade_count`.

### `GET /api/config-drift`

Permission: `view`. Returns changed fields compared with the stored baseline.

### `POST /api/config-drift/baseline`

Permission: `configure`.

Response: `{"success": true, "baseline_nodes": 12}`.

## Integrations and Alerts

### `POST /api/gns3/sync`

Permission: `export`.

With `GNS3_SERVER_URL` and `GNS3_PROJECT_ID`, creates nodes and links through the GNS3 v2 API. Without those settings, returns a safe preview payload.

### `POST /api/alerts/preview`

Permission: `view`.

Request: `{"channel": "teams"}` or `{"channel": "email"}`.

### `POST /api/alerts/email`

Permission: `configure`.

Request: optional `{"recipient": "ops@example.com"}`. Uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `ALERT_EMAIL_TO`.

### `POST /api/alerts/teams`

Permission: `configure`. Sends the generated payload when `TEAMS_WEBHOOK_URL` is configured.

### `GET /api/export/gns3`

Permission: `export`. Returns the GNS3-compatible topology export.

### `GET /api/export/packet_tracer`

Permission: `export`. Returns the Packet Tracer-compatible topology export.

### `POST /api/export/cisco_config`

Permission: `configure`.

Request:

```json
{"node_id": "r1"}
```

Response includes `success`, `node_id`, and generated Cisco IOS `config`.
