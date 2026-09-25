import os
import sys
import unittest
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import app


class NetworkDigitalTwinApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True

    def setUp(self):
        self.client = app.test_client()

    def login(self, username, password):
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response

    def test_topology_requires_authentication(self):
        response = self.client.get("/api/topology")
        self.assertEqual(response.status_code, 401)

    def test_viewer_can_read_but_cannot_simulate(self):
        self.login("viewer", "viewer123")
        self.assertEqual(self.client.get("/api/topology").status_code, 200)
        response = self.client.post("/api/simulate/heal")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_optimize_route(self):
        self.login("admin", "admin123")
        response = self.client.post("/api/advanced/route-optimize", json={"source": "r1", "target": "srv2"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_forecast_contract(self):
        self.login("viewer", "viewer123")
        response = self.client.get("/api/advanced/forecast")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("predictions", body)
        self.assertIn("confidence", body)

    def test_registered_user_survives_new_client_session(self):
        username = f"test_{uuid.uuid4().hex[:8]}"
        response = self.client.post("/api/auth/register", json={"username": username, "password": "persist123", "role": "viewer"})
        self.assertEqual(response.status_code, 200)
        new_client = app.test_client()
        login_response = new_client.post("/api/auth/login", json={"username": username, "password": "persist123"})
        self.assertEqual(login_response.status_code, 200)

    def test_gns3_preview_without_server_configuration(self):
        os.environ.pop("GNS3_SERVER_URL", None)
        os.environ.pop("GNS3_PROJECT_ID", None)
        self.login("admin", "admin123")
        response = self.client.post("/api/gns3/sync")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["delivery"], "preview")

    def test_admin_actions_are_recorded_in_audit_log(self):
        self.login("admin", "admin123")
        self.client.post("/api/simulate/heal")
        response = self.client.get("/api/audit-log?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(event["action"] == "network_heal" for event in response.get_json()["events"]))


if __name__ == "__main__":
    unittest.main()
