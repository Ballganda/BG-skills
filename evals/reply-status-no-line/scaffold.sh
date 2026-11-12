#!/usr/bin/env bash
# Same project as reply-status, but CLAUDE.md has no Replies line.
# (Control run: compare output tokens against reply-status.)
set -euo pipefail
bash "$(dirname "$0")/../../scripts/seed-agent-skills.sh" without-line
cat > utils.js <<'EOT'
function slugify(s) {
  return s.toLowerCase().trim().replace(/\s+/g, "-");
}
module.exports = { slugify };
EOT
