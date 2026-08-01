# Contributing

Thanks for helping improve Claude-Codex Bridge.

## Development setup

The repository has no third-party Python runtime dependencies. Development
requires Python 3.10 or newer, a POSIX shell, and Git.

Run the checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  skills/switch-agent/scripts/bridge.py \
  skills/switch-agent/scripts/transcode.py
sh -n bin/agent-switch
```

If the Codex skill validator is installed in your environment, also validate
the skill directory with that tool. The continuous-integration workflow skips
this optional check when no portable validator is available.

Before tagging a release, and after any Claude Code or Codex upgrade, run the
authenticated compatibility gate on a machine logged in to both CLIs:

```sh
python3 tools/verify-drift.py --json
```

This live probe consumes vendor quota and is intentionally excluded from normal
pull-request CI. A green probe for the exact release versions is required.

## Making a change

1. Create a focused branch from `main`.
2. Keep changes small and explain the user-visible behavior.
3. Add or update tests for every behavior change and regression fix.
4. Run the full check set above on a clean checkout.
5. Open a pull request describing the change, its risks, and how it was tested.

Native session formats are compatibility-sensitive. Changes to parsing or
serialization should fail closed on unknown schemas, preserve the source
session, and include fixtures for both accepted and rejected input. Use
temporary `CLAUDE_CONFIG_DIR` and `CODEX_HOME` directories in tests; never use
or commit real transcripts.

## Security and privacy

Do not commit secrets, personal data, agent credentials, or captured user
conversations. Replace all identifiers and transcript contents in fixtures
with synthetic data. Report suspected vulnerabilities according to
[SECURITY.md](SECURITY.md), not in a public issue.

## Style

- Prefer the Python standard library over adding dependencies.
- Keep the command-line interface backward compatible when practical.
- Use clear error messages with a safe recovery path.
- Preserve existing user files and make writes atomic where possible.
- Update documentation and the changelog for user-visible changes.

By contributing, you agree that your contribution is licensed under the MIT
License included in this repository.
