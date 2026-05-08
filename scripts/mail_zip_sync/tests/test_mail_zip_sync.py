from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.mail_zip_sync.mail_zip_sync import (
    ZipSyncError,
    apply_package,
    create_package,
    save_state,
    sha256_file,
    snapshot_files,
)


class MailZipSyncTests(unittest.TestCase):
    def test_create_and_apply_changed_and_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            (source / "main.py").write_text('print("draft")\n', encoding="utf-8")
            (source / "render.py").write_text("QUALITY = 'low'\n", encoding="utf-8")
            (target / "main.py").write_text('print("draft")\n', encoding="utf-8")
            (target / "render.py").write_text("QUALITY = 'low'\n", encoding="utf-8")

            state_path = source / ".mail_zip_sender_state.json"
            save_state(state_path, snapshot_files(source, ["**/*"], []))

            (source / "main.py").write_text('print("final")\n', encoding="utf-8")
            (source / "shotgrid.py").write_text("SHOT = 'SH010'\n", encoding="utf-8")

            package = create_package(source, source / ".mail_zip_outbox", state_path)
            backup_dir = apply_package(target, package.path, target / "backups")

            self.assertEqual((target / "main.py").read_text(encoding="utf-8"), 'print("final")\n')
            self.assertEqual((target / "render.py").read_text(encoding="utf-8"), "QUALITY = 'low'\n")
            self.assertEqual((target / "shotgrid.py").read_text(encoding="utf-8"), "SHOT = 'SH010'\n")
            self.assertEqual((backup_dir / "main.py").read_text(encoding="utf-8"), 'print("draft")\n')

    def test_apply_refuses_conflicting_target_file(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            (source / "main.py").write_text('print("draft")\n', encoding="utf-8")
            (target / "main.py").write_text('print("company edit")\n', encoding="utf-8")

            state_path = source / ".mail_zip_sender_state.json"
            save_state(state_path, snapshot_files(source, ["**/*"], []))

            (source / "main.py").write_text('print("final")\n', encoding="utf-8")
            package = create_package(source, source / ".mail_zip_outbox", state_path)

            with self.assertRaisesRegex(ZipSyncError, "Target file changed"):
                apply_package(target, package.path, target / "backups")

            self.assertEqual((target / "main.py").read_text(encoding="utf-8"), 'print("company edit")\n')

    def test_create_package_excludes_config_and_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir)
            (source / "main.py").write_text('print("draft")\n', encoding="utf-8")
            state_path = source / ".mail_zip_sender_state.json"
            save_state(state_path, snapshot_files(source, ["**/*"], []))

            (source / "main.py").write_text('print("final")\n', encoding="utf-8")
            (source / "sender_config.json").write_text('{"password": "secret"}\n', encoding="utf-8")
            (source / ".mail_zip_outbox").mkdir()
            (source / ".mail_zip_outbox" / "old.zip").write_text("secret\n", encoding="utf-8")

            package = create_package(source, source / ".mail_zip_outbox", state_path)
            package_text = package.path.read_bytes()

            self.assertEqual([item["path"] for item in package.manifest["files"]], ["main.py"])
            self.assertNotIn(b"secret", package_text)
            self.assertEqual(package.manifest["files"][0]["sha256"], sha256_file(source / "main.py"))


if __name__ == "__main__":
    unittest.main()
