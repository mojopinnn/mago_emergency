import importlib.util
import os
import tempfile
import unittest
import uuid
from pathlib import Path


STORE_FILE = Path(__file__).resolve().parents[1] / "mago_emergency" / "store.py"


def load_store(store_path: Path):
    os.environ["MAGO_STORE_PATH"] = str(store_path)
    module_name = f"mago_store_under_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MagoStorePersistenceTest(unittest.TestCase):
    def test_emergencies_and_subscriptions_survive_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "store.json"
            store = load_store(store_path)

            subscription = store.PushSubscription(
                endpoint="https://push.example/subscription",
                keys={"p256dh": "p256dh-key", "auth": "auth-key"},
            )
            store.save_subscription(101, subscription)
            emergency = store.create_emergency(
                shot_id=77,
                shot_code="SHOT_001",
                project_name="Demo",
                assignee_ids=[101],
            )
            store.increment_reminder(emergency.id)
            store.acknowledge_emergency(emergency.id)
            store.respond_to_emergency(
                emergency.id,
                store.ResponseType.REMOTE_WITHIN_10,
            )

            reloaded = load_store(store_path)
            reloaded_sub = reloaded.get_subscription(101)
            reloaded_emergency = reloaded.get_emergency(emergency.id)

            self.assertIsNotNone(reloaded_sub)
            self.assertEqual(reloaded_sub.endpoint, subscription.endpoint)
            self.assertIsNotNone(reloaded_emergency)
            self.assertEqual(reloaded_emergency.status, reloaded.EmergencyStatus.RESPONDED)
            self.assertEqual(
                reloaded_emergency.response_type,
                reloaded.ResponseType.REMOTE_WITHIN_10,
            )
            self.assertEqual(reloaded_emergency.reminder_count, 1)


if __name__ == "__main__":
    unittest.main()
