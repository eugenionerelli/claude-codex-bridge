# Security policy

## Supported versions

Security fixes are applied to the latest tagged release. The `main` branch may
contain unreleased changes and is supported on a best-effort basis. Older
releases are not maintained unless a release note explicitly says otherwise.

## Reporting a vulnerability

Please use the repository's private **Report a vulnerability** form under the
Security tab. Include:

- the affected version and operating system;
- the smallest reproducible example;
- the expected and observed behavior;
- the potential impact; and
- any suggested mitigation, if known.

Do not include credentials, session transcripts, access tokens, or other
private data in a report. Use synthetic values in reproductions. Please do not
open a public issue for an unpatched vulnerability.

Maintainers will acknowledge a complete report as soon as practical, keep the
reporter informed while it is investigated, and coordinate disclosure after a
fix or mitigation is available.

## Security boundaries

Claude Code and Codex session formats are vendor-owned and may change without
notice. A format compatibility failure is not automatically a security issue,
but any behavior that exposes secrets, writes outside the intended session
directory, corrupts an existing session, or bypasses an approval boundary
should be reported privately.

The bridge should be tested with isolated configuration directories and
synthetic transcripts. Never attach a real production transcript to a public
bug report.
