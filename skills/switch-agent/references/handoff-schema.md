# Continuity and handoff schemas

The bridge has two complementary persistence models:

- v0.3 native continuity: transcript plus automatic capsule, tracked in
  `.agent-bridge/continuity.json` (`agent-bridge.continuity/v1`).
- legacy curated handoff: semantic draft and sealed capsule, stored in
  `draft.json`, `handoff.json`, and `current.md`.

All bridge JSON/Markdown state is local, mode `0600`, and excluded from Git by
the installer. Vendor target sessions are also created as private `0600` files.

## Native continuity ledger

`continuity.json` is bound to one project ID and contains `tasks`. Each task is
an independent chat lane with:

- `active_agent`: current side of the lane;
- `sessions.claude` and `sessions.codex`: native ID, canonical `cwd`, status,
  and update time;
- `transfers`: ordered lineage for that lane.

A transfer record contains:

- `transfer_id`: content-derived identifier over task, direction, source
  session/hash, capsule hash, mode, transcoder version, and size/tool options;
- `parent_transfer_id`: previous transfer in the lane, if any;
- `status`: `planned`, `ready`, `opened`, or `orphaned` when the source changed
  during the atomic target publication;
- `mode`: `native-transcript+capsule` or `capsule-fallback`;
- `source`: agent, native session ID/path, stable SHA-256, detected CLI version,
  and selection method;
- `target`: agent, preplanned native ID/path, plus initial byte length and hash
  after publication;
- `capsule`: SHA-256 and path to `continuity-current.md`;
- `integrity.plan_sha256`: checksum of the immutable source/target plan and its
  lineage, verified before every retry;
- transcoder configuration, fallback reason, and timestamps.

The target identity is planned before writing. Retrying identical input finds
the same transfer record. If the target exists, the bridge verifies its initial
byte prefix; native history appended later is allowed, while collision or
replacement is rejected. The source session is read-only and is never edited.
It is hashed again immediately before and after target publication; a concurrent
append blocks opening and leaves an explicitly orphaned target for audit.

## Source selection

Select the source session in this order:

1. explicit `--source-session`;
2. the source-side session stored in the selected task lane;
3. compatible legacy hook state for the same canonical project;
4. the newest valid vendor session whose declared `cwd` matches the project.

Always provide an explicit ID for the first hop of a lane when multiple chats
share one `cwd`. Claude IDs must be UUIDv4; new Codex targets use UUIDv7.

## Transcript semantics

The neutral transfer representation contains visible `user` and `assistant`
turns. It removes target-regenerated environment/system/developer injections,
Claude sidechains, and hidden thinking/reasoning. Consecutive equal roles are
merged. Tool calls are dropped, compacted, or included according to `--tools`;
tool output remains explicitly untrusted data.

A transfer begins with an untrusted-history prologue and ends with:

1. an explicit pending-work/compaction boundary;
2. the automatic project capsule as a user data block;
3. an assistant boundary when needed so the synthetic history does not leave a
   user turn falsely marked as completed.

Codex encrypted compaction summaries are not decryptable. Available raw visible
history is retained and an omission boundary is inserted. Global character
budget truncation keeps the head and tail and records omitted counts.

`--transcript auto` falls back to capsule-only on a source error;
`--transcript required` propagates the error; `--transcript off` intentionally
skips source parsing. Reading can be explicitly relaxed for an unknown source
version, but creating the target is always gated to tested format prefixes.

## Automatic deterministic capsule

`continuity-current.md` contains `agent-bridge.capsule/v1` with task, direction,
canonical project root, project snapshot, verification limitations, and a
continuation rule. It contains no authored summary and is stable for identical
project state.

For Git projects the snapshot records branch, HEAD, upstream, operation in
progress, porcelain status, and SHA-256 fingerprints for status, staged and
unstaged diffs, plus bounded untracked metadata/content fingerprints. It stores
diff statistics rather than raw diffs. Non-Git projects use a bounded metadata
fingerprint and recent non-sensitive paths.

Paths matching the sensitive-file policy are omitted from exported names,
diffs, statistics, and content hashes. The capsule records only their count and
the resulting verification limitation.

## Legacy semantic handoff

`draft.json` contains agent-authored fields; `handoff.json` binds them to
project identity, source session, deterministic snapshot, timestamps, and an
integrity checksum; `current.md` is the compact hook payload.

Required semantic intent:

- `objective` and `definition_of_done` describe the current user outcome;
- `completed`, `current_focus`, and `next_action` distinguish finished work
  from the exact continuation point (`next_action` is required);
- `decisions`, `validation`, `open_questions`, and `blockers` must be factual;
- `do_not_redo`, `background_processes`, and
  `required_environment_names` carry operational constraints without values;
- `notes` holds only essential context that fits nowhere else.

Never include hidden reasoning, `.env` contents, auth material, secret values,
signed URLs, or unnecessary personal data. A checksum detects corruption, not
malicious rewriting by a process with access to the same account.
