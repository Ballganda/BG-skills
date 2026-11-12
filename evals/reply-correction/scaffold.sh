#!/usr/bin/env bash
# Seeds a small project whose CLAUDE.md holds the Agent skills block with the
# Replies line (taken from bg-setup's template).
set -euo pipefail
bash "$(dirname "$0")/../../scripts/seed-agent-skills.sh" with-line
cat > utils.js <<'EOT'
function slugify(s) {
  return s.toLowerCase().trim().replace(/\s+/g, "-");
}
module.exports = { slugify };
EOT
