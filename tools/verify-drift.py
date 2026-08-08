#!/usr/bin/env python3
"""Verifica anti-deriva: prova il round trip contro i binari realmente installati.

I formati di sessione di Claude Code e Codex non sono un contratto pubblico fra
fornitori. Cambiano senza preavviso, e un transcoder che oggi funziona domani
può scrivere un file che l'altro agente accetta ma non capisce. Tutti i progetti
paragonabili dichiarano una matrice di compatibilità fissata a mano e invecchiano
in silenzio.

Questo script sostituisce la dichiarazione con una misura. Crea un progetto
temporaneo, semina una sessione Claude Code reale con marcatori casuali, la
trasferisce a Codex, chiede a Codex di ricordarli senza leggere file, riporta la
sessione a Claude Code e richiede la stessa cosa. Se un marcatore non torna, il
formato è cambiato sotto di noi e lo script fallisce con un rapporto leggibile.

Uso:

    python3 tools/verify-drift.py                 # round trip completo
    python3 tools/verify-drift.py --direction claude-to-codex
    python3 tools/verify-drift.py --json          # per la CI

Costa due chiamate a Claude Code e una a Codex nel round trip completo, quindi
consuma quota reale.
Va eseguito dopo un aggiornamento di una delle due CLI, non a ogni commit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TRANSCODE = SCRIPT_DIR.parent / "skills" / "switch-agent" / "scripts" / "transcode.py"
CODEX_BUNDLED = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))

CLAUDE_PROBE_MODEL = os.environ.get("DRIFT_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
STEP_TIMEOUT = int(os.environ.get("DRIFT_STEP_TIMEOUT", "600"))


class DriftFailure(RuntimeError):
    """Il formato è cambiato: un marcatore non è tornato dall'altro lato."""


class Inconclusive(RuntimeError):
    """La prova non è arrivata in fondo per cause esterne al formato.

    Quota esaurita, credenziali mancanti, rete assente. Va tenuto distinto dalla
    deriva vera: un controllo che segnala rosso quando finiscono i crediti viene
    ignorato dopo la seconda volta, e allora non serve più a niente.
    """


INFRA_SIGNS = (
    "usage limit",
    "rate limit",
    "quota",
    "401 unauthorized",
    "403 forbidden",
    "missing bearer",
    "not logged in",
    "authentication",
    "connection refused",
    "network is unreachable",
    "temporary failure in name resolution",
    "credit",
)


def classify(detail: str) -> None:
    """Solleva Inconclusive se il fallimento è di infrastruttura, non di formato."""
    lowered = detail.lower()
    for sign in INFRA_SIGNS:
        if sign in lowered:
            raise Inconclusive(detail)


def find_claude() -> str:
    found = shutil.which("claude")
    if not found:
        raise DriftFailure("Claude Code non trovato nel PATH.")
    return found


def find_codex() -> str:
    found = shutil.which("codex")
    if found:
        return found
    if CODEX_BUNDLED.is_file() and os.access(CODEX_BUNDLED, os.X_OK):
        return str(CODEX_BUNDLED)
    raise DriftFailure(
        "Codex non trovato: né nel PATH né dentro ChatGPT.app."
    )


def version_of(executable: str, args: list[str]) -> str:
    try:
        out = subprocess.run(
            [executable, *args], capture_output=True, text=True, timeout=60
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise DriftFailure(f"Impossibile leggere la versione di {executable}: {exc}") from exc
    match = re.search(r"\d+\.\d+\.\d+[A-Za-z0-9.\-]*", out)
    if not match:
        raise DriftFailure(f"Versione non riconoscibile da {executable}: {out.strip()!r}")
    return match.group(0)


def run(cmd: list[str], cwd: str, what: str) -> str:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=STEP_TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        raise DriftFailure(f"{what}: scaduto dopo {STEP_TIMEOUT}s.") from exc
    if proc.returncode != 0:
        detail = salient(proc.stderr, proc.stdout)
        classify(detail)
        raise DriftFailure(f"{what}: uscita {proc.returncode}. {detail}")
    return proc.stdout


# Le CLI ritentano in loop e riempiono stderr di righe identiche: la causa vera è
# quasi sempre l'ultima riga distinta, non le venti di riconnessione prima.
NOISE = re.compile(r"^\s*(ERROR:\s*Reconnecting|warning:|\s*$)", re.I)


def salient(stderr: str | None, stdout: str | None, limit: int = 300) -> str:
    """Ultima riga informativa, scartando il rumore dei ritentativi."""
    lines = [
        line.strip()
        for line in ((stderr or "") + "\n" + (stdout or "")).splitlines()
        if line.strip() and not NOISE.match(line)
    ]
    if not lines:
        return "nessun dettaglio disponibile."
    seen: list[str] = []
    for line in reversed(lines):
        if line not in seen:
            seen.append(line)
        if len(seen) == 2:
            break
    return " | ".join(reversed(seen))[:limit]


def transcode(
    source: str,
    target: str,
    project: str,
    session: str | None,
    *,
    allow_unsupported: bool = False,
) -> dict:
    cmd = [
        sys.executable, str(TRANSCODE), "switch",
        "--from", source, "--to", target, "--project", project,
    ]
    if session:
        cmd += ["--session", session]
    if allow_unsupported:
        # Il caso per cui esiste questo strumento: è uscita una versione nuova
        # delle CLI e va deciso se il cancello si può allargare. Senza questo,
        # il cancello blocca la prova che servirebbe proprio ad aggiornarlo.
        cmd += ["--allow-unsupported-version"]
    out = run(cmd, project, f"transcode {source}->{target}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise DriftFailure(f"transcode {source}->{target}: output non JSON: {out[:400]!r}") from exc


def mint_markers(count: int = 3) -> list[str]:
    """Marcatori che non possono stare nei dati di addestramento né in un file."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    out = []
    for _ in range(count):
        word = "".join(secrets.choice(alphabet) for _ in range(6))
        out.append(f"{word}-{secrets.randbelow(9000) + 1000}")
    return out


def claude_project_dir(project: str) -> Path:
    encoded = "".join(
        character if (character.isascii() and character.isalnum()) else "-"
        for character in project
    )
    return CLAUDE_HOME / "projects" / encoded


def seed_claude(claude: str, project: str, markers: list[str]) -> tuple[str, Path]:
    prompt = (
        "Annota questi codici di verifica del progetto e non fare altro: "
        + ", ".join(markers)
        + ". Rispondi solo con la parola: annotato."
    )
    run([claude, "--model", CLAUDE_PROBE_MODEL, "-p", prompt], project, "seed Claude")
    directory = claude_project_dir(project)
    sessions = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        raise DriftFailure(f"Nessuna sessione Claude creata in {directory}")
    return sessions[0].stem, sessions[0]


def remove_claude_probe(path: Path, project: str) -> None:
    """Remove only an exact session created inside this probe's unique project."""
    expected_parent = claude_project_dir(project)
    if path.parent != expected_parent or path.suffix != ".jsonl":
        raise DriftFailure(f"Rifiuto cleanup Claude fuori dal progetto probe: {path}")
    path.unlink(missing_ok=True)
    try:
        expected_parent.rmdir()
    except OSError:
        pass


QUESTION = (
    "Senza leggere nessun file e senza cercare: elenca i codici di verifica del "
    "progetto di cui abbiamo parlato, separati da virgola, e nient'altro."
)


def ask_codex(codex: str, project: str, session: str) -> str:
    return run(
        [
            codex, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
            "-c", "model_reasoning_effort=low", "resume", session, QUESTION,
        ],
        project,
        "interrogazione Codex",
    )


def ask_claude(claude: str, project: str, session: str) -> str:
    return run(
        [claude, "--model", CLAUDE_PROBE_MODEL, "--resume", session, "-p", QUESTION],
        project,
        "interrogazione Claude",
    )


def missing(markers: list[str], answer: str) -> list[str]:
    return [m for m in markers if m not in answer]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--direction",
        choices=("round-trip", "claude-to-codex", "codex-to-claude"),
        default="round-trip",
    )
    parser.add_argument("--json", action="store_true", help="Rapporto leggibile dalla CI.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Conserva progetto e sessioni probe per l'ispezione.",
    )
    parser.add_argument(
        "--allow-unsupported-version",
        action="store_true",
        help="Prova comunque una versione di CLI fuori dal cancello, per decidere se allargarlo.",
    )
    args = parser.parse_args()

    started = time.time()
    report: dict = {"ok": False, "steps": [], "direction": args.direction}
    workdir: str | None = None
    project: str | None = None
    claude: str | None = None
    codex: str | None = None
    claude_probe_paths: list[Path] = []
    codex_probe_ids: list[str] = []

    try:
        claude = find_claude()
        codex = find_codex()
        report["claude_version"] = version_of(claude, ["--version"])
        report["codex_version"] = version_of(codex, ["--version"])
        if not TRANSCODE.is_file():
            raise DriftFailure(f"transcode.py non trovato in {TRANSCODE}")

        workdir = tempfile.mkdtemp(prefix="drift-")
        # Un nome con spazio e accento: i bug di quoting si nascondono qui.
        project_dir = Path(workdir) / "progetto di prova é"
        project_dir.mkdir()
        project = str(project_dir.resolve())
        report["project"] = project

        markers = mint_markers()
        report["markers"] = markers

        claude_session, claude_source_path = seed_claude(claude, project, markers)
        claude_probe_paths.append(claude_source_path)
        report["steps"].append({"step": "seed-claude", "session": claude_session, "ok": True})

        if args.direction in ("round-trip", "claude-to-codex"):
            forward = transcode(
                "claude", "codex", project, claude_session,
                allow_unsupported=args.allow_unsupported_version,
            )
            codex_session = forward["target_session_id"]
            codex_probe_ids.append(codex_session)
            answer = ask_codex(codex, project, codex_session)
            lost = missing(markers, answer)
            report["steps"].append({
                "step": "claude-to-codex",
                "session": codex_session,
                "messages": forward.get("messages"),
                "missing": lost,
                "ok": not lost,
            })
            if lost:
                raise DriftFailure(
                    f"Codex non ha ricordato {lost} dopo il trasferimento. "
                    "Il formato di sessione Codex è probabilmente cambiato."
                )
        else:
            codex_session = None

        if args.direction in ("round-trip", "codex-to-claude"):
            if codex_session is None:
                codex_session = transcode(
                    "claude", "codex", project, claude_session,
                    allow_unsupported=args.allow_unsupported_version,
                )[
                    "target_session_id"
                ]
                codex_probe_ids.append(codex_session)
            back = transcode(
                "codex", "claude", project, codex_session,
                allow_unsupported=args.allow_unsupported_version,
            )
            new_claude_session = back["target_session_id"]
            claude_probe_paths.append(Path(back["target_file"]))
            answer = ask_claude(claude, project, new_claude_session)
            lost = missing(markers, answer)
            report["steps"].append({
                "step": "codex-to-claude",
                "session": new_claude_session,
                "messages": back.get("messages"),
                "missing": lost,
                "ok": not lost,
            })
            if lost:
                raise DriftFailure(
                    f"Claude Code non ha ricordato {lost} dopo il ritorno. "
                    "Il formato di sessione Claude Code è probabilmente cambiato."
                )

        report["ok"] = True

    except Inconclusive as exc:
        report["inconclusive"] = True
        report["error"] = str(exc)
    except DriftFailure as exc:
        report["error"] = str(exc)
    except Exception as exc:  # pragma: no cover - rete di sicurezza per la CI
        report["error"] = f"errore inatteso: {exc!r}"
    finally:
        if not args.keep:
            cleanup_errors: list[str] = []
            if codex and project:
                for session_id in dict.fromkeys(codex_probe_ids):
                    try:
                        run(
                            [codex, "delete", "--force", session_id],
                            project,
                            f"cleanup sessione Codex {session_id}",
                        )
                    except (DriftFailure, Inconclusive) as exc:
                        cleanup_errors.append(str(exc))
            if project:
                for path in dict.fromkeys(claude_probe_paths):
                    try:
                        remove_claude_probe(path, project)
                    except (OSError, DriftFailure) as exc:
                        cleanup_errors.append(str(exc))
            if workdir:
                shutil.rmtree(workdir, ignore_errors=True)
            if cleanup_errors:
                report["cleanup_errors"] = cleanup_errors
                report["ok"] = False
                cleanup_summary = (
                    "Verifica conclusa, ma il cleanup sicuro dei probe è fallito."
                )
                if report.get("error"):
                    report["cleanup_error"] = cleanup_summary
                else:
                    report["error"] = cleanup_summary

    report["seconds"] = round(time.time() - started, 1)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        state = (
            "verde" if report["ok"]
            else "INCONCLUSIVA" if report.get("inconclusive")
            else "ROSSO"
        )
        print(f"verifica anti-deriva: {state} in {report['seconds']}s")
        print(f"  Claude Code {report.get('claude_version', '?')}")
        print(f"  Codex       {report.get('codex_version', '?')}")
        for step in report["steps"]:
            mark = "ok " if step["ok"] else "NO "
            detail = f" mancanti={step['missing']}" if step.get("missing") else ""
            print(f"  {mark}{step['step']}{detail}")
        if report.get("error"):
            print(f"  causa: {report['error']}")

    # 0 verde, 1 deriva vera, 2 inconcludente. La CI deve poter distinguere
    # "il formato è cambiato" da "sono finiti i crediti".
    if report["ok"]:
        return 0
    return 2 if report.get("inconclusive") else 1


if __name__ == "__main__":
    raise SystemExit(main())
