#!/usr/bin/env bash
# Seeds a workspace whose CLAUDE.md holds the Agent skills block with the
# Replies line (taken from bg-setup's template), as the reply cases do.
set -euo pipefail
bash "$(dirname "$0")/../../scripts/seed-agent-skills.sh" with-line
