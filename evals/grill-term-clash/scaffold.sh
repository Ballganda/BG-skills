#!/usr/bin/env bash
# Seeds a CLAUDE.md whose Agent skills block holds the Replies line (taken from
# bg-setup's template, as the reply cases do), and the fixture glossary the
# prompt's wording clashes with.
set -euo pipefail
bash "$(dirname "$0")/../../scripts/seed-agent-skills.sh" with-line
cat > GLOSSARY.md <<'EOF'
# Ordering

How customers place orders and how the shop handles them until delivery.

## Language

**Order**:
A customer's request to buy one or more items, placed in a single checkout.
_Avoid_: Purchase, basket

**Line Item**:
One product and its quantity within an Order.
_Avoid_: Order line, entry

**Dispatch**:
The moment an Order leaves the warehouse.
_Avoid_: Shipping, fulfilment

**Cancellation**:
Withdrawing an entire Order before Dispatch, so nothing is sent and nothing is charged.
_Avoid_: Void, abort
EOF
