/bg-skills:grill Plan for the order service rework. Three things are already decided:

1. Order storage moves from CRUD tables to an event-sourced log. We compared it with adding an audit table and with change data capture, and picked event sourcing because auditors must be able to replay any order's full history. Going back later would mean rebuilding every read model.
2. Orders stay in our existing Postgres cluster. It is the only database we run and nobody proposed anything else.
3. The "Export" button on the orders page gets relabelled "Download CSV".

Grill me on the rest of the plan.
