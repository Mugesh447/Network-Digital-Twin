# Network Digital Twin Test Report

## Test Command

```powershell
python -m unittest discover -s tests -v
```

Test source: [tests/test_backend.py](../tests/test_backend.py)

## Coverage

| Area | Test | Expected result |
|---|---|---|
| Authentication | Unauthenticated topology request | Returns `401 Authentication required` |
| Authentication | Login with built-in account | Returns session token and HTTP-only cookie |
| Authentication | Registered user login from a new client | Succeeds after account creation |
| RBAC | Viewer reads topology | Returns `200` |
| RBAC | Viewer attempts simulation | Returns `403` |
| RBAC | Admin runs route optimization | Returns `200` with an optimized path |
| Forecast | Viewer requests predictive forecast | Returns `200` with `predictions` and `confidence` |
| Route optimization | Admin optimizes `r1` to `srv2` | Returns path nodes, path links, latency, and reroute status |
| GNS3 | Sync without GNS3 configuration | Returns safe `preview` delivery mode |

## Security Assertions

- Protected APIs reject requests without a session.
- Viewer accounts cannot mutate topology or trigger simulation.
- Operator accounts can simulate, export, and optimize routes.
- Admin accounts can configure topology and baselines.
- Registered passwords are stored as hashes in SQLite.

## Expected Result

```text
----------------------------------------------------------------------
Ran 6 tests in ...s

OK
```

The test suite does not require a live GNS3 server, SMTP server, or browser. GNS3 behavior is tested in preview mode when `GNS3_SERVER_URL` is not configured.

## Manual Checks

For an end-to-end browser check:

1. Start the app with `python app.py`.
2. Log in as `viewer` and confirm read-only access.
3. Log in as `admin` and run Auto Reroute.
4. Open AI Copilot and confirm forecast/risk cards load.
5. Configure GNS3 variables and run GNS3 Sync.
