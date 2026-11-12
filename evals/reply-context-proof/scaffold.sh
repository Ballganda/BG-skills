#!/usr/bin/env bash
# Seeds the same CLAUDE.md as reply-status (Agent skills block with the
# Replies line) plus a canary line, through the shared seeding script.
set -euo pipefail
bash "$(dirname "$0")/../../scripts/seed-agent-skills.sh" with-line canary
