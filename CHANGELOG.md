# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-08-01

### Added

- Bidirectional native transcript transfer between Claude Code and Codex into
  newly created target sessions.
- Per-task continuity records, project identity checks, locking, Git and
  filesystem drift detection, secret redaction, and an operational capsule
  fallback.
- Crash-safe target planning, immutable plan checksums, concurrent source-write
  detection, and private atomic vendor-session publication.
- Optional safe-by-default AgentBridge integration for live parallel agent
  collaboration.
- Project installation, diagnostics, hooks, launch, resume, and recovery
  commands through `agent-switch`.
- Cross-platform continuous integration for supported POSIX environments.
- Authenticated, quota-aware native format drift probe with manual/scheduled
  self-hosted CI support.
