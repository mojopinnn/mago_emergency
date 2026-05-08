import importlib.util
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


MAGO_DIR = Path(__file__).resolve().parents[1] / "mago_emergency"
MAIN_FILE = MAGO_DIR / "main.py"


def load_main(store_path: Path):
    os.environ["MAGO_STORE_PATH"] = str(store_path)
    os.environ["ADMIN_TOKEN"] = "admin-secret"
    os.environ["WEBHOOK_SECRET"] = "webhook-secret"
    for name in ["main", "store", "push", "shotgrid_client", "scheduler", "cloudflare_kv"]:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(MAGO_DIR))
    try:
        module_name = f"mago_main_under_test_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, MAIN_FILE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(MAGO_DIR))


class MagoMainSecurityTest(unittest.TestCase):
    def test_admin_routes_require_configured_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_main(Path(tmp) / "store.json")
            client = TestClient(module.app)

            response = client.get("/admin/users")

            self.assertEqual(response.status_code, 401)

    def test_webhook_requires_configured_secret_before_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_main(Path(tmp) / "store.json")
            client = TestClient(module.app)

            response = client.post(
                "/sg_webhook",
                data={"selected_ids": "123", "entity_type": "Task"},
            )

            self.assertEqual(response.status_code, 401)

    def test_webhook_rejects_invalid_selected_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_main(Path(tmp) / "store.json")
            client = TestClient(module.app)

            response = client.post(
                "/sg_webhook",
                headers={"X-MAGO-Webhook-Secret": "webhook-secret"},
                data={"selected_ids": "not-a-number", "entity_type": "Task"},
            )

            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
