from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFY_DRIFT = ROOT / "tools" / "verify-drift.py"
SPEC = importlib.util.spec_from_file_location("verify_drift", VERIFY_DRIFT)
assert SPEC is not None and SPEC.loader is not None
verify_drift = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_drift)


class DriftVerifierTests(unittest.TestCase):
    def test_markers_are_unique_and_missing_is_exact(self) -> None:
        markers = verify_drift.mint_markers(20)

        self.assertEqual(len(markers), len(set(markers)))
        self.assertTrue(all("-" in marker for marker in markers))
        self.assertEqual(verify_drift.missing(markers, " ".join(markers[:-1])), markers[-1:])

    def test_claude_project_encoding_handles_spaces_and_accents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "claude-home"
            with mock.patch.object(verify_drift, "CLAUDE_HOME", home):
                path = verify_drift.claude_project_dir("/tmp/progetto é uno")

        self.assertEqual(path.parent, home / "projects")
        self.assertEqual(path.name, "-tmp-progetto---uno")

    def test_cleanup_removes_only_exact_probe_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "claude-home"
            project = "/tmp/probe é"
            with mock.patch.object(verify_drift, "CLAUDE_HOME", home):
                directory = verify_drift.claude_project_dir(project)
                directory.mkdir(parents=True)
                session = directory / "11111111-1111-4111-8111-111111111111.jsonl"
                session.write_text("{}\n", encoding="utf-8")
                verify_drift.remove_claude_probe(session, project)
                self.assertFalse(session.exists())
                self.assertFalse(directory.exists())

                outside = home / "unrelated.jsonl"
                outside.parent.mkdir(parents=True, exist_ok=True)
                outside.write_text("{}\n", encoding="utf-8")
                with self.assertRaises(verify_drift.DriftFailure):
                    verify_drift.remove_claude_probe(outside, project)
                self.assertTrue(outside.exists())


if __name__ == "__main__":
    unittest.main()
