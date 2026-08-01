# Claude ↔ Codex Bridge

Claude ↔ Codex Bridge v0.3 moves an active coding conversation into a new,
native session of the other agent while keeping the same project directory or
Git worktree. The default transfer combines the visible transcript with a
deterministic project capsule, records bidirectional lineage, and opens the
destination directly. The source session is never rewritten.

The result is a real `claude --resume <id>` or Codex thread, not a prompt that
asks the next model to reconstruct the work from a summary. On macOS, Codex is
opened with `codex://threads/<id>` and Claude in a resumed Terminal session; no
prefilled prompt and no extra Enter are required on the primary path.

> Native session transcoding is experimental. Claude Code and Codex do not
> publish these on-disk schemas as a cross-vendor API. The implementation is
> empirically tested, structurally validated, and version-gated rather than
> assumed stable.

Verified end to end on macOS on 2026-08-01 with Claude Code `2.1.220` and
Codex `0.146.0-alpha.9.2`: Claude → Codex → Claude preserved facts introduced
on both sides; the Codex rollout became visible from the deep link alone,
without a bootstrap turn, and both target files remained `0600` after native
resume. Hermetic tests use isolated vendor homes and never touch real chats.
An additional 8.1 MB real-world transcript round trip retained facts buried in
the middle while reducing the visible transfer to about 64,000 characters.

## Quick start

Requirements: Python 3.10+, Claude Code, and Codex. Git is optional. Automatic
opening is implemented for macOS; on other systems use `--no-open` and run the
printed resume command.

```bash
./bin/agent-switch install --hooks "/path/to/project"
./bin/agent-switch doctor --project "/path/to/project"
```

The examples below assume `agent-switch` is linked into your `PATH` as shown
under Installation. Otherwise, replace it with the checkout's
`./bin/agent-switch`.

The shortest form infers the source side automatically:

```bash
agent-switch to codex --task feature-auth --project "/path/to/project"
agent-switch to claude --task feature-auth --project "/path/to/project"
```

Inside either agent, asking “passa a Codex” or “passa a Claude” activates the
installed `switch-agent` skill and performs the same operation.

Switch a chat from Claude Code to Codex and back in the same lane:

```bash
agent-switch switch --from claude --to codex \
  --task feature-auth --project "/path/to/project"

agent-switch switch --from codex --to claude \
  --task feature-auth --project "/path/to/project"
```

`--task` identifies an independent chat lane and defaults to `main`. From the
agents, the equivalent requests are `/switch-agent codex` in Claude Code and
`$switch-agent claude` in Codex.

Finish or interrupt the current model turn before switching so the source JSONL
is stable. For the first transfer in a lane, or whenever several source chats
share the same working directory, select the exact one explicitly:

```bash
agent-switch switch --from claude --to codex --task feature-auth \
  --source-session 00000000-0000-4000-8000-000000000000 \
  --project "/path/to/project"
```

## What `switch` transfers

The default `--transcript auto` flow:

1. resolves the source session from `--source-session`, the task ledger, hook
   state, or the most recent valid session bound to the same `cwd`;
2. reads a stable, user-owned source JSONL and validates its structure, session
   identity, working directory, and supported CLI version;
3. maps visible user/assistant turns into a neutral representation, redacts
   probable secrets, and compacts tool activity;
4. appends a capsule containing the verified Git/filesystem snapshot and
   continuation boundary;
5. creates a private native target session, records its lineage, and opens it.

Transcript modes are explicit:

- `--transcript auto` (default): use transcript plus capsule; if the transcript
  is absent or incompatible, create a capsule-only native session.
- `--transcript required`: stop instead of falling back.
- `--transcript off`: do not read the source transcript; transfer only the
  capsule.

Tool calls default to `--tools compact --tool-chars 600`. Use `drop` for the
smallest and most private transfer, or `full` when tool outputs are essential.
All modes still honor `--max-chars` (120,000 by default), which preserves the
head and tail and inserts an explicit omission marker when needed.

Use `--dry-run` to inspect the plan without writing or opening anything, and
`--no-open` to create the target but only print its deep link/resume command.
`--allow-unsupported-version` relaxes the *source read* gate only; target
writing remains version-gated.

## Multi-chat lineage and retries

Each project keeps a private `.agent-bridge/continuity.json` ledger. Every task
stores its Claude and Codex session IDs plus an ordered transfer lineage. A
transfer ID is derived from the source snapshot, capsule, task, direction, and
transcoding options. Repeating the same switch reuses the planned target and
verifies its original byte prefix instead of creating duplicates or overwriting
history. The immutable transfer plan is checksummed before reuse. Native messages
appended after the switch remain intact; if the source changes during publication,
the target stays closed and is marked `orphaned` instead of being presented as
current.

Use different task names for unrelated chats in the same repository:

```bash
agent-switch switch --from claude --to codex --task bug-142 --project "$PWD"
agent-switch switch --from claude --to codex --task refactor-api --project "$PWD"
agent-switch status --project "$PWD"
```

Task names are 1–64 characters from `A-Z`, `a-z`, `0-9`, `.`, `_`, and `-`;
`.`/`..`, trailing dots, traversal, and reserved device names are rejected.

## Installation

Clone the repository, then install it into each project where you want native
switching:

```bash
git clone https://github.com/eugenionerelli/claude-codex-bridge.git
cd claude-codex-bridge
./bin/agent-switch install --hooks "/path/to/project"
```

The installer links the same skill into `.agents/skills/switch-agent` and
`.claude/skills/switch-agent`, creates private state under `.agent-bridge/`, and
adds local hook handlers without deleting existing ones. Backups of extended
hook files live under `${TMPDIR}/agent-bridge-<uid>/backups/<project-id>/`.
Generated local state and untracked hook files are added to Git's local exclude.

Optional global command:

```bash
mkdir -p "$HOME/.local/bin"
ln -s "/path/to/Claude-Codex-Bridge/bin/agent-switch" \
  "$HOME/.local/bin/agent-switch"
```

After moving a project, run `install --rebind --hooks PROJECT`, then `doctor`.

### Uninstall

There is intentionally no destructive automatic uninstall. To remove a project
installation, first verify and unlink only the two skill symlinks, remove only
the Agent Bridge entries from `.codex/hooks.json` and
`.claude/settings.local.json`, and remove the corresponding block from
`.git/info/exclude`. Move `.agent-bridge/` to Trash only after deciding that its
local history is no longer needed. Remove `~/.local/bin/agent-switch` only if it
is the symlink you created. These steps preserve all vendor session files.

## Legacy capsule workflow

The curated checkpoint workflow remains available when you want to edit the
handoff manually or avoid native transcript parsing:

```bash
agent-switch prepare --from claude --to codex --project "/path/to/project"
# Edit .agent-bridge/draft.json
agent-switch finalize --project "/path/to/project"
agent-switch launch --to codex --project "/path/to/project"
```

It validates and seals `draft.json`, checks drift, and injects `current.md` via
hooks. This legacy launcher can retain its prompt-based behavior; use `switch`
for direct native resume with no manual submission.

## Optional live collaboration

[`AgentBridge`](https://github.com/raysonmeng/agent-bridge) solves a different
workflow: keeping Claude and Codex alive together and relaying messages for
cross-review. If Bun and `@raysonmeng/agentbridge` are installed, this wrapper
forces its safe mode (`AGENTBRIDGE_SAFE=1`, plus `--safe` on launch):

```bash
agent-switch live doctor --project "$PWD"
agent-switch live init --task review --project "$PWD"
agent-switch live launch claude --task review --project "$PWD"
agent-switch live launch codex --task review --project "$PWD"
agent-switch live resume --task review --project "$PWD"
agent-switch live stop --task review --project "$PWD"
```

The Claude development channel used by AgentBridge may still require a local
consent prompt on launch. Live mode is optional and does not replace transcript
migration.

For the supported one-way Claude → Codex case, OpenAI's official
[`codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) provides
`/codex:transfer`. This project adds the reverse direction, task lineage,
capsule fallback, and a single CLI workflow; it does not claim to replace the
official importer.

[`ccl`](https://github.com/luongnv89/ccl) keeps and redacts imported transcripts
in its own store, then injects them into a one-shot `-p` invocation. MCP command
relays such as `codex-bridge`, and similar one-shot bridges, also hand context
to another process. These are useful adjacent workflows; they do not create a
new native resumable, interactive destination session, which is the persistence
model used here.

### Why the engine remains in-tree

Native Claude/Codex transcoding already exists in several community projects;
this repository does not claim otherwise. The bundled standard-library engine
is retained because it is small enough to audit together with the workflow
layer and is verified against the exact installed CLI builds. Delegating to a
second engine today would add another version and supply-chain boundary while
the closest dedicated alternative is pinned to older builds. A future external
adapter remains possible, but is not on the critical path.

`tools/verify-drift.py` is the compatibility canary: it mints unpredictable
markers, creates a real Claude session, performs the native round trip, asks
both agents to recall the markers without file access, and exits non-zero on
loss. Run it after either CLI changes:

```bash
python3 tools/verify-drift.py --json
```

The probe consumes two Claude calls and one Codex call, then removes only the
probe sessions it created. It is therefore a mandatory release/upgrade gate,
not a per-commit test. The `Vendor format drift` workflow supports manual and
weekly runs on a private macOS runner authenticated to both CLIs; standard CI
only validates its non-networked command surface and never consumes quota.

## Security and privacy

- Target JSONL and bridge state are created with mode `0600`; newly created
  vendor-session and local runtime directories use `0700`. Writes are atomic,
  refuse symlinked/unowned vendor paths, and never overwrite an unrelated
  session.
- The source is hashed around transcoding and immediately before and after
  target publication; a changing, incomplete, oversized, wrong-`cwd`, or
  malformed session is rejected.
- Supported source format prefixes are currently Claude Code `2.1.*` and Codex
  `0.146.*`. New Claude targets use UUIDv4 and new Codex targets UUIDv7.
  `doctor` reports compatibility. Every target write is gated.
- Probable tokens, credentials, private keys, signed URLs, and secret
  assignments are masked and counted. This is best-effort redaction, not a DLP
  guarantee. Do not transfer a transcript containing secrets you cannot copy.
- Sensitive project paths and contents are excluded from capsule exports and
  diff material is hashed rather than embedded. The transcript itself can
  still contain values previously typed or printed by a tool.
- The checksum and lineage detect accidental corruption and target collisions;
  they are not signatures against another process that can rewrite your home
  or workspace.

The bridge never commits, resets, stashes, checks out, creates worktrees, or
changes the source session. With cloud-synced projects, its process lock remains
machine-local: do not use two computers as simultaneous writers.

## Known limitations

- Hidden thinking/reasoning, permission state, background processes, and
  ephemeral tool state are not transferable.
- Codex encrypted compaction summaries cannot be decrypted. The bridge keeps
  available raw visible history and inserts a compaction boundary, but context
  present only inside the encrypted summary is unavailable.
- Environment/system/developer injections are dropped because the destination
  recreates its own current environment. Claude sidechains are not copied.
- Compact tool mode omits results and clips calls; full mode is larger and can
  expose more sensitive output. Neither mode recreates a running tool process.
- Native formats are empirical and may change without notice. An unsupported
  source falls back in `auto`, blocks in `required`, and an unsupported target
  always blocks. Run `doctor` after every Claude or Codex upgrade.
- Automatic opening is macOS-specific. The printed Claude/Codex resume command
  is the portable fallback.

## Troubleshooting

- **Codex is not in `PATH`:** resolution order is `CODEX_EXECUTABLE`, `PATH`,
  then `/Applications/ChatGPT.app/Contents/Resources/codex`. Set
  `CODEX_EXECUTABLE` if your app is elsewhere.
- **Wrong source chat:** finish the source turn and pass `--source-session`.
  Keep separate work under distinct `--task` names.
- **Format warning after an upgrade:** run `doctor`; use `auto` for safe capsule
  fallback or `required` when transcript continuity is mandatory. Do not force
  an unsupported target format.
- **GUI opening fails:** rerun the identical command with `--no-open`, then use
  the emitted `claude --resume` or `codex resume -C ...` command.
- **Project moved or identity changed:** run `install --rebind --hooks PROJECT`
  followed by `doctor`.

## In breve (Italiano)

Il comando principale è `agent-switch switch`: copia la conversazione visibile in
una nuova sessione nativa dell'altro agente, aggiunge lo snapshot operativo del
progetto e apre direttamente la chat, senza prompt precompilato né Invio manuale.
`--task` separa più chat nello stesso progetto; `--transcript required` pretende
un transcript trasferibile, mentre `off` usa solo la capsule. I formati interni sono
sperimentali e version-gated: dopo ogni aggiornamento eseguire `agent-switch
doctor`.
