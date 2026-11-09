#!/usr/bin/env bash
# Seeds the fixture glossary the prompt's wording clashes with.
set -euo pipefail
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
