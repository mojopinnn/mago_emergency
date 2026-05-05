from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mail_patch_sync import apply_patch, generate_patch, patch_changed_paths  # noqa: E402


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class MailPatchSyncTests(unittest.TestCase):
    def test_generate_and_apply_multi_file_patch(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            for repo in (source, target):
                run(repo, "init")
                run(repo, "config", "user.email", "test@example.com")
                run(repo, "config", "user.name", "Test User")
                (repo / "main.py").write_text('print("draft")\n', encoding="utf-8")
                (repo / "render.py").write_text("QUALITY = 'low'\n", encoding="utf-8")
                run(repo, "add", ".")
                run(repo, "commit", "-m", "initial")

            (source / "main.py").write_text('print("final")\n', encoding="utf-8")
            (source / "render.py").write_text("QUALITY = 'high'\n", encoding="utf-8")
            (source / "shotgrid.py").write_text("SHOT = 'SH010'\n", encoding="utf-8")

            patch = generate_patch(source, source / "outbox")

            self.assertIn("main.py", patch_changed_paths(patch.path))
            self.assertIn("render.py", patch_changed_paths(patch.path))
            self.assertIn("shotgrid.py", patch_changed_paths(patch.path))

            backup_dir = apply_patch(target, patch.path, target / "backups")

            self.assertEqual((target / "main.py").read_text(encoding="utf-8"), 'print("final")\n')
            self.assertEqual((target / "render.py").read_text(encoding="utf-8"), "QUALITY = 'high'\n")
            self.assertEqual((target / "shotgrid.py").read_text(encoding="utf-8"), "SHOT = 'SH010'\n")
            self.assertEqual((backup_dir / "main.py").read_text(encoding="utf-8"), 'print("draft")\n')

    def test_generate_patch_excludes_config_and_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir)
            run(source, "init")
            run(source, "config", "user.email", "test@example.com")
            run(source, "config", "user.name", "Test User")
            (source / "main.py").write_text('print("draft")\n', encoding="utf-8")
            run(source, "add", ".")
            run(source, "commit", "-m", "initial")

            (source / "main.py").write_text('print("final")\n', encoding="utf-8")
            (source / "sender_config.json").write_text('{"password": "secret"}\n', encoding="utf-8")
            (source / "mail_patch_outbox").mkdir()
            (source / "mail_patch_outbox" / "old.patch").write_text("secret\n", encoding="utf-8")

            patch = generate_patch(source, source / "mail_patch_outbox")
            patch_text = patch.path.read_text(encoding="utf-8")

            self.assertIn("main.py", patch_changed_paths(patch.path))
            self.assertNotIn("sender_config.json", patch_changed_paths(patch.path))
            self.assertNotIn("mail_patch_outbox/old.patch", patch_changed_paths(patch.path))
            self.assertNotIn("secret", patch_text)


if __name__ == "__main__":
    unittest.main()
