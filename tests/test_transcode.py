from __future__ import annotations

import datetime as dt
import importlib.util
import inspect
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import uuid
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TRANSCODE_PATH = ROOT / "skills" / "switch-agent" / "scripts" / "transcode.py"

SPEC = importlib.util.spec_from_file_location("agent_switch_transcode_tests", TRANSCODE_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(f"Impossibile importare {TRANSCODE_PATH}")
transcode = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transcode
SPEC.loader.exec_module(transcode)


CLAUDE_SESSION = "11111111-1111-4111-8111-111111111111"
CODEX_SESSION = "018f1234-5678-7abc-8def-0123456789ab"
SUPPORTED_CLAUDE_VERSION = transcode.CLAUDE_VERSION_FALLBACK
SUPPORTED_CODEX_VERSION = transcode.CODEX_VERSION_FALLBACK


class TranscodeTests(unittest.TestCase):
    """Tests hermetici: nessun accesso alle home/sessioni vendor reali."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-transcode-test-")
        self.root = Path(self.temporary.name)
        self.project = self.root / "Progetto con spazio e accento è"
        self.project.mkdir()
        self.claude_home = self.root / "claude-home"
        self.codex_home = self.root / "codex-home"
        self.home_patch = mock.patch.multiple(
            transcode,
            CLAUDE_HOME=self.claude_home,
            CODEX_HOME=self.codex_home,
        )
        self.home_patch.start()

    def tearDown(self) -> None:
        self.home_patch.stop()
        self.temporary.cleanup()

    @staticmethod
    def write_jsonl(path: Path, rows: list[dict]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def claude_path(self, session_id: str = CLAUDE_SESSION) -> Path:
        return (
            self.claude_home
            / "projects"
            / transcode.claude_project_dirname(str(self.project))
            / f"{session_id}.jsonl"
        )

    def write_claude_fixture(
        self,
        *,
        session_id: str = CLAUDE_SESSION,
        cwd: Path | None = None,
        version: str = SUPPORTED_CLAUDE_VERSION,
        rows: list[dict] | None = None,
    ) -> Path:
        source_cwd = str(cwd or self.project)
        if rows is None:
            rows = [
                {
                    "type": "user",
                    "parentUuid": None,
                    "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "timestamp": "2026-08-01T10:00:00.000Z",
                    "sessionId": session_id,
                    "cwd": source_cwd,
                    "version": version,
                    "message": {"role": "user", "content": "Fatto alfa"},
                },
                {
                    "type": "assistant",
                    "parentUuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "uuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "timestamp": "2026-08-01T10:00:01.000Z",
                    "sessionId": session_id,
                    "cwd": source_cwd,
                    "version": version,
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Ricevuto alfa"}],
                    },
                },
            ]
        return self.write_jsonl(self.claude_path(session_id), rows)

    def codex_path(self, session_id: str = CODEX_SESSION, *, day: str = "2026/08/01") -> Path:
        return (
            self.codex_home
            / "sessions"
            / day
            / f"rollout-2026-08-01T12-00-00-{session_id}.jsonl"
        )

    def write_codex_fixture(
        self,
        *,
        session_id: str = CODEX_SESSION,
        cwd: Path | None = None,
        version: str = SUPPORTED_CODEX_VERSION,
        include_meta: bool = True,
        path: Path | None = None,
    ) -> Path:
        source_cwd = str(cwd or self.project)
        rows: list[dict] = []
        if include_meta:
            rows.append(
                {
                    "timestamp": "2026-08-01T10:00:00.000Z",
                    "type": "session_meta",
                    "payload": {
                        "session_id": session_id,
                        "id": session_id,
                        "timestamp": "2026-08-01T10:00:00.000Z",
                        "cwd": source_cwd,
                        "originator": "codex_cli_rs",
                        "cli_version": version,
                        "source": "cli",
                        "thread_source": "user",
                        "model_provider": "openai",
                        "instructions": None,
                    },
                }
            )
        rows.extend(
            [
                {
                    "timestamp": "2026-08-01T10:00:01.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Fatto beta"}],
                    },
                },
                {
                    "timestamp": "2026-08-01T10:00:02.000Z",
                    "type": "response_item",
                    "payload": {"type": "reasoning", "summary": []},
                },
                {
                    "timestamp": "2026-08-01T10:00:03.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Ricevuto beta"}],
                    },
                },
            ]
        )
        return self.write_jsonl(path or self.codex_path(session_id), rows)

    def test_claude_parser_maps_text_tools_and_drops_thinking(self) -> None:
        rows = [
            {
                "type": "user",
                "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "Ricorda ORTENSIA"},
            },
            {
                "type": "assistant",
                "uuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "non trasferire"},
                        {"type": "text", "text": "Memorizzato"},
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/tmp/esempio"},
                        },
                    ],
                },
            },
        ]
        path = self.write_claude_fixture(rows=rows)

        transcript = transcode.read_claude(path, tools="compact", tool_chars=40)

        self.assertEqual(transcript.cwd, str(self.project))
        self.assertEqual(transcript.source_session_id, CLAUDE_SESSION)
        self.assertEqual([message.role for message in transcript.messages], ["user", "assistant", "assistant"])
        self.assertIn("ORTENSIA", transcript.messages[0].text)
        self.assertEqual(transcript.messages[2].kind, "tool")
        self.assertIn("[strumento Read]", transcript.messages[2].text)
        self.assertEqual(transcript.dropped.get("thinking"), 1)

    def test_claude_active_branch_traverses_attachment_nodes(self) -> None:
        rows = [
            {
                "type": "user",
                "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "parentUuid": None,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "prima"},
            },
            {
                "type": "attachment",
                "uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                "parentUuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
            },
            {
                "type": "assistant",
                "uuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "parentUuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "dopo allegato"}],
                },
            },
            {
                "type": "last-prompt",
                "leafUuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "sessionId": CLAUDE_SESSION,
            },
        ]
        path = self.write_claude_fixture(rows=rows)

        transcript = transcode.read_claude(path, tools="compact", tool_chars=40)

        self.assertEqual([message.text for message in transcript.messages], ["prima", "dopo allegato"])

    def test_claude_preserves_disconnected_resume_segments_and_excludes_branches(self) -> None:
        rows = [
            {
                "type": "user",
                "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "parentUuid": None,
                "isSidechain": False,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "FATTO-PRE-RESUME"},
            },
            {
                "type": "assistant",
                "uuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "parentUuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "isSidechain": False,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "assistant", "content": "PRE-CONFERMATO"},
            },
            {
                "type": "last-prompt",
                "leafUuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "sessionId": CLAUDE_SESSION,
            },
            {
                "type": "user",
                "uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                "parentUuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "isSidechain": False,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "RAMO-NON-VISIBILE"},
            },
            {
                "type": "assistant",
                "uuid": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                "parentUuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "isSidechain": True,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "assistant", "content": "SIDECHAIN-NON-VISIBILE"},
            },
            {
                "type": "user",
                "uuid": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                "parentUuid": None,
                "isSidechain": False,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "FATTO-POST-RESUME"},
            },
            {
                "type": "assistant",
                "uuid": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                "parentUuid": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                "isSidechain": False,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "assistant", "content": "POST-CONFERMATO"},
            },
            {
                "type": "last-prompt",
                "leafUuid": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                "sessionId": CLAUDE_SESSION,
            },
        ]
        path = self.write_claude_fixture(rows=rows)

        transcript = transcode.read_claude(path, tools="compact", tool_chars=40)

        self.assertEqual(
            [message.text for message in transcript.messages],
            ["FATTO-PRE-RESUME", "PRE-CONFERMATO", "FATTO-POST-RESUME", "POST-CONFERMATO"],
        )
        self.assertEqual(transcript.dropped.get("branch"), 1)
        self.assertEqual(transcript.dropped.get("sidechain"), 1)

    def test_codex_parser_maps_messages_and_drops_reasoning(self) -> None:
        path = self.write_codex_fixture()

        transcript = transcode.read_codex(path, tools="compact", tool_chars=40)

        self.assertEqual(transcript.cwd, str(self.project))
        self.assertEqual(transcript.source_session_id, CODEX_SESSION)
        self.assertEqual(
            [(message.role, message.text) for message in transcript.messages],
            [("user", "Fatto beta"), ("assistant", "Ricevuto beta")],
        )
        self.assertEqual(transcript.dropped.get("reasoning"), 1)

    def test_codex_identity_requires_filename_id_and_session_id_to_match(self) -> None:
        other_id = "018f1234-5678-7abc-8def-0123456789ac"
        scenarios = ("filename", "id", "session_id")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                path = self.codex_path(CODEX_SESSION)
                self.write_codex_fixture(path=path)
                rows = list(transcode.iter_jsonl(path))
                if scenario == "filename":
                    mismatched_path = self.codex_path(other_id)
                    path.rename(mismatched_path)
                    path = mismatched_path
                else:
                    rows[0]["payload"][scenario] = other_id
                    self.write_jsonl(path, rows)
                with self.assertRaisesRegex(
                    transcode.TranscodeError, "Identità Codex incoerente"
                ):
                    transcode.read_codex(path, tools="compact", tool_chars=40)
                path.unlink()

    def test_find_codex_rollout_fails_closed_on_identity_mismatch(self) -> None:
        other_id = "018f1234-5678-7abc-8def-0123456789ac"
        path = self.write_codex_fixture(path=self.codex_path(other_id))

        with self.assertRaisesRegex(transcode.TranscodeError, "Identità Codex incoerente"):
            transcode.find_codex_rollout(str(self.project), other_id)

    def test_structural_canaries_reject_malformed_vendor_messages(self) -> None:
        claude_rows = [
            {
                "type": "user",
                "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "parentUuid": None,
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "assistant", "content": "ruolo errato"},
            }
        ]
        claude_path = self.write_claude_fixture(rows=claude_rows)
        with self.assertRaisesRegex(transcode.TranscodeError, "Canary Claude"):
            transcode.read_claude(claude_path, tools="compact", tool_chars=40)

        codex_path = self.write_codex_fixture()
        codex_rows = list(transcode.iter_jsonl(codex_path))
        codex_rows[1]["payload"]["content"] = {"unexpected": True}
        self.write_jsonl(codex_path, codex_rows)
        with self.assertRaisesRegex(transcode.TranscodeError, "Canary Codex"):
            transcode.read_codex(codex_path, tools="compact", tool_chars=40)

    def test_codex_parser_marks_compaction_boundary_without_nested_duplication(self) -> None:
        path = self.write_codex_fixture()
        rows = list(transcode.iter_jsonl(path))
        rows.insert(
            2,
            {
                "timestamp": "2026-08-01T10:00:01.500Z",
                "type": "compacted",
                "payload": {
                    "window_number": 2,
                    "replacement_history": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "NON DUPLICARE"}],
                        }
                    ],
                },
            },
        )
        self.write_jsonl(path, rows)

        transcript = transcode.read_codex(path, tools="compact", tool_chars=40)

        texts = [message.text for message in transcript.messages]
        self.assertEqual(sum("NON DUPLICARE" in text for text in texts), 0)
        self.assertEqual(sum("Boundary di compaction" in text for text in texts), 1)
        self.assertEqual(transcript.dropped.get("encrypted-compaction-summary"), 1)

    def test_codex_parser_accepts_native_resume_session_meta_boundary(self) -> None:
        path = self.write_codex_fixture()
        rows = list(transcode.iter_jsonl(path))
        resumed_meta = json.loads(json.dumps(rows[0]))
        resumed_meta["timestamp"] = "2026-08-01T10:05:00.000Z"
        resumed_meta["payload"]["timestamp"] = "2026-08-01T10:05:00.000Z"
        rows.insert(3, resumed_meta)
        self.write_jsonl(path, rows)

        transcript = transcode.read_codex(path, tools="compact", tool_chars=40)

        self.assertEqual(transcript.source_session_id, CODEX_SESSION)
        self.assertEqual(transcript.cwd, str(self.project))

    def test_round_trip_writers_are_parseable_in_both_directions(self) -> None:
        source = transcode.Transcript(
            cwd=str(self.project),
            source_agent="claude",
            source_session_id=CLAUDE_SESSION,
            messages=[
                transcode.Msg("user", "ZANZIBAR-4471"),
                transcode.Msg("assistant", "MAGELLANO-88"),
            ],
        )
        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CODEX_VERSION):
            codex_id, codex_path = transcode.write_codex(source, source.messages)
        parsed_codex = transcode.read_codex(codex_path, tools="compact", tool_chars=40)

        self.assertEqual(uuid.UUID(codex_id).version, 7)
        self.assertEqual([m.text for m in parsed_codex.messages], ["ZANZIBAR-4471", "MAGELLANO-88"])

        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CLAUDE_VERSION):
            claude_id, claude_path = transcode.write_claude(parsed_codex, parsed_codex.messages)
        parsed_claude = transcode.read_claude(claude_path, tools="compact", tool_chars=40)

        self.assertEqual(uuid.UUID(claude_id).version, 4)
        self.assertEqual([m.text for m in parsed_claude.messages], ["ZANZIBAR-4471", "MAGELLANO-88"])

    def test_uuid7_is_deterministic_with_injected_entropy(self) -> None:
        moment = dt.datetime(2026, 8, 1, 10, 11, 12, 345000, tzinfo=dt.timezone.utc)
        with mock.patch.object(transcode.secrets, "token_bytes", return_value=b"\x00" * 16):
            first = transcode.uuid7(moment)
            second = transcode.uuid7(moment)

        parsed = uuid.UUID(first)
        self.assertEqual(first, second)
        self.assertEqual(parsed.version, 7)
        self.assertEqual(parsed.variant, uuid.RFC_4122)

    def test_find_codex_rollout_matches_exact_cwd_not_latest_other_project(self) -> None:
        wanted = self.write_codex_fixture(path=self.codex_path(CODEX_SESSION, day="2026/08/01"))
        other_project = self.root / "altro-progetto"
        other_project.mkdir()
        other_id = "018f1234-5678-7abc-8def-0123456789ac"
        other = self.write_codex_fixture(
            session_id=other_id,
            cwd=other_project,
            path=self.codex_path(other_id, day="2026/08/02"),
        )
        os.utime(wanted, (1, 1))
        os.utime(other, (2, 2))

        selected = transcode.find_codex_rollout(str(self.project), None)

        self.assertEqual(selected, wanted)

    def test_find_codex_rollout_refuses_fallback_to_unrelated_cwd(self) -> None:
        other_project = self.root / "altro-progetto"
        other_project.mkdir()
        self.write_codex_fixture(cwd=other_project)

        with self.assertRaises(transcode.TranscodeError):
            transcode.find_codex_rollout(str(self.project), None)

    def test_explicit_session_must_match_requested_cwd(self) -> None:
        other_project = self.root / "altro-progetto"
        other_project.mkdir()
        self.write_codex_fixture(cwd=other_project)

        with self.assertRaises(transcode.TranscodeError):
            transcode.load_transcript(
                "codex",
                str(self.project),
                CODEX_SESSION,
                tools="compact",
                tool_chars=40,
            )

    def test_claude_session_id_rejects_path_traversal_and_non_uuid(self) -> None:
        directory = self.claude_path().parent
        directory.mkdir(parents=True)
        (directory.parent / "escape.jsonl").write_text("{}\n", encoding="utf-8")
        (directory / "not-a-uuid.jsonl").write_text("{}\n", encoding="utf-8")

        for unsafe_id in ("../escape", "not-a-uuid"):
            with self.subTest(session_id=unsafe_id):
                with self.assertRaises(transcode.TranscodeError):
                    transcode.find_claude_session(str(self.project), unsafe_id)

    def test_codex_session_id_rejects_glob_metacharacters(self) -> None:
        self.write_codex_fixture()

        with self.assertRaises(transcode.TranscodeError):
            transcode.find_codex_rollout(str(self.project), "*")

    def test_validate_target_path_rejects_codex_traversal(self) -> None:
        unsafe = (
            self.codex_home
            / "sessions"
            / "2026"
            / "08"
            / "01"
            / ".."
            / f"rollout-2026-08-01T12-00-00-{CODEX_SESSION}.jsonl"
        )

        with self.assertRaises(transcode.TranscodeError):
            transcode.validate_target_path("codex", str(self.project), CODEX_SESSION, unsafe)

    def test_validate_target_path_rejects_invalid_or_mismatched_codex_date(self) -> None:
        invalid_calendar_date = (
            self.codex_home
            / "sessions"
            / "2026"
            / "13"
            / "40"
            / f"rollout-2026-13-40T12-00-00-{CODEX_SESSION}.jsonl"
        )
        mismatched_date = (
            self.codex_home
            / "sessions"
            / "2026"
            / "08"
            / "01"
            / f"rollout-2026-08-02T12-00-00-{CODEX_SESSION}.jsonl"
        )

        for path in (invalid_calendar_date, mismatched_date):
            with self.subTest(path=path):
                with self.assertRaises(transcode.TranscodeError):
                    transcode.validate_target_path(
                        "codex", str(self.project), CODEX_SESSION, path
                    )

    def test_postprocess_enforces_budget_for_four_or_fewer_large_messages(self) -> None:
        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="claude",
            source_session_id=CLAUDE_SESSION,
            messages=[
                transcode.Msg("user", "A" * 5_000),
                transcode.Msg("assistant", "B" * 5_000),
            ],
        )

        transcode.postprocess(transcript, max_chars=1_000)

        self.assertLessEqual(transcript.char_count, 1_000)
        self.assertGreater(transcript.truncated_chars, 0)

    def test_tool_secret_is_redacted_before_clipping(self) -> None:
        private_key = "-----BEGIN PRIVATE KEY-----\n" + ("A" * 500)
        rows = [
            {
                "type": "user",
                "uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {"role": "user", "content": "usa tool"},
            },
            {
                "type": "assistant",
                "uuid": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "parentUuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "sessionId": CLAUDE_SESSION,
                "cwd": str(self.project),
                "version": SUPPORTED_CLAUDE_VERSION,
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Shell", "input": {"key": private_key}}
                    ],
                },
            },
        ]
        path = self.write_claude_fixture(rows=rows)

        transcript = transcode.read_claude(path, tools="compact", tool_chars=80)

        self.assertNotIn("BEGIN PRIVATE KEY", transcript.messages[-1].text)
        self.assertIn("[REDACTED:private-key]", transcript.messages[-1].text)
        self.assertGreaterEqual(transcript.redactions.get("private-key", 0), 1)

    def test_secure_reader_rejects_incomplete_jsonl(self) -> None:
        path = self.claude_path()
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")

        with self.assertRaises(transcode.TranscodeError):
            list(transcode.iter_jsonl(path))

    def test_claude_schema_gate_rejects_unknown_major_version(self) -> None:
        self.write_claude_fixture(version="99.0.0")

        with self.assertRaises(transcode.TranscodeError):
            transcode.load_transcript(
                "claude",
                str(self.project),
                CLAUDE_SESSION,
                tools="compact",
                tool_chars=40,
            )

    def test_codex_schema_gate_rejects_unknown_major_version(self) -> None:
        self.write_codex_fixture(version="99.0.0")

        with self.assertRaises(transcode.TranscodeError):
            transcode.load_transcript(
                "codex",
                str(self.project),
                CODEX_SESSION,
                tools="compact",
                tool_chars=40,
            )

    def test_codex_schema_gate_checks_every_native_resume_boundary(self) -> None:
        path = self.write_codex_fixture()
        rows = list(transcode.iter_jsonl(path))
        resumed_meta = json.loads(json.dumps(rows[0]))
        resumed_meta["payload"]["cli_version"] = "99.0.0"
        rows.append(resumed_meta)
        self.write_jsonl(path, rows)

        with self.assertRaises(transcode.TranscodeError):
            transcode.load_transcript(
                "codex",
                str(self.project),
                CODEX_SESSION,
                tools="compact",
                tool_chars=40,
            )

    def test_codex_schema_gate_requires_session_meta_first(self) -> None:
        self.write_codex_fixture(include_meta=False)

        with self.assertRaises(transcode.TranscodeError):
            transcode.load_transcript(
                "codex",
                str(self.project),
                CODEX_SESSION,
                tools="compact",
                tool_chars=40,
            )

    def test_claude_writer_sets_private_permissions(self) -> None:
        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="codex",
            source_session_id=CODEX_SESSION,
        )
        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CLAUDE_VERSION):
            _, path = transcode.write_claude(
                transcript,
                [transcode.Msg("user", "privato"), transcode.Msg("assistant", "ok")],
            )

        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_codex_writer_sets_private_permissions(self) -> None:
        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="claude",
            source_session_id=CLAUDE_SESSION,
        )
        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CODEX_VERSION):
            _, path = transcode.write_codex(
                transcript,
                [transcode.Msg("user", "privato"), transcode.Msg("assistant", "ok")],
            )

        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    @unittest.skipUnless(hasattr(os, "symlink"), "Il sistema non supporta symlink")
    def test_claude_writer_refuses_symlinked_project_session_directory(self) -> None:
        project_directory = self.claude_path().parent
        project_directory.parent.mkdir(parents=True)
        escape = self.root / "claude-escape"
        escape.mkdir()
        project_directory.symlink_to(escape, target_is_directory=True)
        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="codex",
            source_session_id=CODEX_SESSION,
        )

        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CLAUDE_VERSION):
            with self.assertRaises((transcode.TranscodeError, OSError)):
                transcode.write_claude(
                    transcript,
                    [transcode.Msg("user", "non uscire"), transcode.Msg("assistant", "ok")],
                )
        self.assertEqual(list(escape.iterdir()), [])

    @unittest.skipUnless(hasattr(os, "symlink"), "Il sistema non supporta symlink")
    def test_codex_writer_refuses_symlinked_sessions_root(self) -> None:
        self.codex_home.mkdir()
        escape = self.root / "codex-escape"
        escape.mkdir()
        (self.codex_home / "sessions").symlink_to(escape, target_is_directory=True)
        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="claude",
            source_session_id=CLAUDE_SESSION,
        )

        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CODEX_VERSION):
            with self.assertRaises((transcode.TranscodeError, OSError)):
                transcode.write_codex(
                    transcript,
                    [transcode.Msg("user", "non uscire"), transcode.Msg("assistant", "ok")],
                )
        self.assertEqual(list(escape.rglob("*")), [])

    def test_idempotent_writer_contract_when_hook_is_available(self) -> None:
        """Exercise an optional stable-ID hook without prescribing its implementation."""
        parameters = inspect.signature(transcode.write_codex).parameters
        id_parameter = next(
            (name for name in ("session_id", "target_session_id", "idempotency_key") if name in parameters),
            None,
        )
        if id_parameter is None:
            self.skipTest("transcode.py non espone ancora un hook di scrittura idempotente")

        transcript = transcode.Transcript(
            cwd=str(self.project),
            source_agent="claude",
            source_session_id=CLAUDE_SESSION,
        )
        messages = [transcode.Msg("user", "stabile"), transcode.Msg("assistant", "ok")]
        kwargs = {id_parameter: CODEX_SESSION}
        with mock.patch.object(transcode, "detect_version", return_value=SUPPORTED_CODEX_VERSION):
            first_id, first_path = transcode.write_codex(transcript, messages, **kwargs)
            first_bytes = first_path.read_bytes()
            second_id, second_path = transcode.write_codex(transcript, messages, **kwargs)

        self.assertEqual((first_id, first_path), (second_id, second_path))
        self.assertEqual(second_path.read_bytes(), first_bytes)


if __name__ == "__main__":
    unittest.main()
