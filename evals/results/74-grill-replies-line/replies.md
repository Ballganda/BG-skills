# Kept Replies and grader votes

## grill-adr-worthy

### with, run 1

Reply:

> Understood: event sourcing, staying on Postgres, and the "Download CSV" label are settled, and you want me to grill you on everything else.
> Round 1 is below: seven open decisions that depend only on those three.
> 
> - The repo holds only `CLAUDE.md`, so I had no code to check your claims against.
> - `docs/agents/domain.md` is referenced in `CLAUDE.md` but doesn't exist.
> - No `GLOSSARY.md` exists yet, so I'll create one when we settle the first term.
> 
> How I'm treating your three decisions:
> - **Event sourcing:** this needs a written decision record (ADR). It's hard to reverse, a future reader will wonder why it was chosen, and you compared real alternatives. See Q1.
> - **Postgres:** no ADR, because nobody proposed an alternative.
> - **"Download CSV" label:** no ADR, because it's a one-line change that's easy to undo.
> 
> ❓ **Q1** - **ADR for event sourcing**: Record why event sourcing beat an audit table and change data capture: auditors must be able to replay the full history, and going back means rebuilding every read model.
> 
> ➡️ Yes, write `docs/adr/0001-event-sourced-order-storage.md` and include the rejected alternatives.
> 
> ---
> 
> ❓ **Q2** - **Event granularity**: Should events be business facts (`OrderPlaced`, `LineItemAdded`, `OrderCancelled`) or generic field changes (`OrderUpdated {field, old, new}`)?
> 
> ➡️ Business facts, named in the past tense, because auditors read intent, not field changes.
> 
> ---
> 
> ❓ **Q3** - **Existing orders**: The current tables only hold each order's latest state, so these orders have no history to replay. Options:
> - (a) Add one `OrderMigrated` snapshot event per order.
> - (b) Rebuild history from logs or backups.
> - (c) Leave old orders in the old tables.
> 
> ➡️ (a), and tell auditors in writing that history before the cutover is a single snapshot.
> 
> ---
> 
> ❓ **Q4** - **What "replay" means for auditors**: Options:
> - (a) A view of an order's state as it stood after any given event.
> - (b) A raw dump of the events.
> - (c) Both.
> 
> ➡️ (a), backed by an event list, because "replay any order's full history" suggests rebuilding the order's state at any point.
> 
> ---
> 
> ❓ **Q5** - **Read model consistency**: Do projections such as the orders page and the CSV update in the same Postgres transaction as the event write, or asynchronously afterwards?
> 
> ➡️ Same transaction for now. Everything runs on one cluster, so that's cheap, and you avoid stale-read bugs.
> 
> ---
> 
> ❓ **Q6** - **Personal data in an immutable log**: Events can't be edited, but erasure requests will still arrive. Options:
> - (a) Keep personal data out of events and reference customers by ID.
> - (b) Encrypt each customer's data with its own key, and delete the key to erase it.
> - (c) Accept that you can't erase.
> 
> ➡️ (a): events hold a `customer_id` only, and personal data stays in a mutable table.
> 
> ---
> 
> ❓ **Q7** - **Scope of "Download CSV"**: Does only the label change, or do the CSV's contents and source change too, now that it would be built from a read model?
> 
> ➡️ Only the label changes: same columns, same contents.

Votes:

- adr-only-when-all-three: PASS PASS PASS (passed)
- no-adr-for-trivial-decisions: PASS (passed)

### with, run 2

Reply:

> Understood: event sourcing, staying on the existing Postgres cluster, and the "Download CSV" relabel are settled, and you want me to grill you on the rest of the plan.
> 
> Round 1 has eight open questions below, and I haven't written anything yet.
> 
> - **Event sourcing**: kept as you decided, because auditors must be able to replay any order's full history.
> - **Postgres**: kept as you decided, because it's the only database you run. It doesn't need an ADR because no alternative was considered.
> - **"Download CSV"**: kept as you decided. It doesn't need an ADR because it's easy to change back.
> - **Repo check**: this repo has no order code, `GLOSSARY.md` or `docs/adr/` yet. So I had nothing to check your claims against.
> 
> ❓ **Q1** - **ADR for event sourcing**: should I record the event-sourcing decision as an ADR? It's hard to reverse, it will surprise a future reader, and you weighed it against an audit table and CDC.
> 
> ➡️ Yes, write `docs/adr/0001-event-sourced-order-storage.md` with the audit-replay reason and the cost of rebuilding read models.
> 
> ---
> 
> ❓ **Q2** - **History for existing orders**: today's CRUD rows hold no real history. The options are to give each existing order one synthetic "imported" event, or to try to rebuild past events from timestamps and logs.
> 
> ➡️ Give each existing order one explicit `OrderImported` snapshot event. Auditors then see clearly that replay starts at migration, and you avoid inventing history.
> 
> ---
> 
> ❓ **Q3** - **Event granularity**: events can be business facts (`OrderPlaced`, `OrderPaid`, `OrderShipped`) or generic field changes (`OrderUpdated{field, old, new}`).
> 
> ➡️ Use business-fact events. Auditors replay intent, not column diffs.
> 
> ---
> 
> ❓ **Q4** - **Read-model consistency**: projections can update in the same Postgres transaction as the event append (consistent immediately), or asynchronously from the log (eventually consistent).
> 
> ➡️ Update the orders-page projection in the same transaction, and update other read models asynchronously. Being on one Postgres cluster makes the same-transaction option cheap.
> 
> ---
> 
> ❓ **Q5** - **Concurrent writes to one order**: two requests can try to change the same order at the same moment.
> 
> ➡️ Use optimistic concurrency: a unique `(order_id, version)` constraint on the event table, with a retry or a conflict error when it's violated.
> 
> ---
> 
> ❓ **Q6** - **Personal data in an immutable log**: erasure requests clash with events you can never change. The options are to keep personal data out of events (store only IDs), encrypt it per customer and delete the key on erasure ("crypto-shredding"), or accept that you can't erase it.
> 
> ➡️ Keep personal data out of events and reference customer IDs only. Fall back to crypto-shredding only for fields that must live in the event.
> 
> ---
> 
> ❓ **Q7** - **Event schema evolution**: event shapes will change over the years. The options are to store a version on each event and convert old versions when reading, or to rewrite old events during migrations.
> 
> ➡️ Store a version on each event and convert old versions when reading. Never rewrite stored events, because rewriting would undermine the audit guarantee.
> 
> ---
> 
> ❓ **Q8** - **Auditor replay surface**: auditors need some way to replay an order. The options are a read-only internal view showing an order's event stream plus its state at any timestamp, a raw SQL/export handoff, or both.
> 
> ➡️ Build a read-only internal view showing the event stream and the state at any timestamp.
> 
> ---
> 
> ❓ **Q9** - **What "Download CSV" contains**: it could export the current state of the listed orders only, or also include event history.
> 
> ➡️ Current state only, with the same columns as today's Export. History stays in the auditor view from Q8.
> 
> Cutover strategy (big-bang, or dual-write then switch) and retiring the old tables both depend on Q2 and Q4, so they come next round.

Votes:

- adr-only-when-all-three: PASS PASS PASS (passed)
- no-adr-for-trivial-decisions: PASS (passed)

### with, run 3

Reply:

> Understood: event sourcing, staying on the existing Postgres cluster and the "Download CSV" label are all settled, and you want me to grill you on the rest of the order service rework.
> 
> The repo has only `CLAUDE.md`, so there's no glossary, ADRs or order code to check against yet. Round 1 is below.
> 
> - **Event sourcing**: I'm treating this as final and building on it. Of your three decisions, it's the only one that meets all three ADR criteria (hard to undo, surprising, a real trade-off).
> - **Postgres**: I'm treating this as settled too. There was no real alternative, so it doesn't need an ADR.
> - **"Download CSV"**: Only the label changes. No questions on this one.
> 
> ❓ **Q1** - **ADR for event sourcing**: Should I record the event sourcing decision as `docs/adr/0001-event-sourced-order-storage.md`? It would list the audit table and change data capture as the options you turned down.
> 
> ➡️ Yes. Without it, someone will suggest "just add an audit table" again within a year.
> 
> ---
> 
> ❓ **Q2** - **What "replay" means to an auditor**: Auditors could get (a) a list of an order's events, (b) the order's state as of any past moment, or (c) both.
> 
> ➡️ Both. Record each event's business time as well as its storage time, so "state as of" means business time.
> 
> ---
> 
> ❓ **Q3** - **History of existing orders**: Your current tables only hold each order's latest state, so its earlier history is gone. Options: (a) start each old order with one `OrderMigrated` event holding its current state, (b) rebuild past events from logs or timestamps, (c) leave old orders in the CRUD tables.
> 
> ➡️ (a). Tell the auditors in writing that full replay for old orders starts at the migration date. Rebuilt history would be made up, which is worse than a gap you've stated openly.
> 
> ---
> 
> ❓ **Q4** - **What an event records**: Events can name business actions (`OrderPlaced`, `LineAdded`, `OrderCancelled`) or record raw field changes (`status changed from A to B`).
> 
> ➡️ Business actions. Auditors replay meaning, not column changes, and field-change events are change data capture again, which you rejected.
> 
> ---
> 
> ❓ **Q5** - **Event store layout in Postgres**: Options: (a) one append-only `order_events` table with a unique `(order_id, version)` that rejects conflicting writes, (b) a table per event type, (c) a dedicated event-store extension.
> 
> ➡️ (a). It uses only plain Postgres, and the unique constraint stops two concurrent writes to the same order.
> 
> ---
> 
> ❓ **Q6** - **How fresh read models are**: Options: (a) update the orders read model in the same transaction that appends the event, (b) update it asynchronously from the log.
> 
> ➡️ (a) for the main orders read model, so users always see their own writes. Use (b) only for heavy reports, the CSV download among them.
> 
> ---
> 
> ❓ **Q7** - **Correcting mistakes**: Events can't be edited. A wrong price or address is either (a) fixed with a correcting event like `LinePriceCorrected`, or (b) edited by an admin in the log.
> 
> ➡️ (a), always. Never edit the log: one edit and auditors can no longer trust any replay.
> 
> ---
> 
> ❓ **Q8** - **Personal data in an immutable log**: Requests to erase customer data clash with events you can't change. Options: (a) events point to customers by ID only, with personal details kept in a separate table you can delete from, (b) encrypt personal fields with a key per customer and delete the key to erase them, (c) accept that personal data stays in the log.
> 
> ➡️ (a). It's the simplest of the three, and erasing a customer never touches the log.
> 
> ---
> 
> ❓ **Q9** - **Changing event formats later**: When the shape of an event changes, you can (a) convert old events to the new shape as they're read, (b) migrate stored events in place, (c) never change an event, only add new types.
> 
> ➡️ (a). Stored events never get rewritten, which keeps the auditors' guarantee intact.
> 
> ---
> 
> I'll ask about the cutover plan (switching everything at once or writing to both stores for a while) next round, because the answer depends on Q3 and Q6.

Votes:

- adr-only-when-all-three: PASS PASS PASS (passed)
- no-adr-for-trivial-decisions: PASS (passed)

### with, run 4

Reply:

> Understood: event sourcing, staying on Postgres and the "Download CSV" label are settled, and you want me to question you on everything else in the order service rework.
> 
> Round 1 is below, covering every open decision that the three settled ones unblock.
> 
> - The repo contains only `CLAUDE.md`, so there's no order code to check your claims against.
> - `docs/agents/domain.md` is referenced in `CLAUDE.md` but doesn't exist.
> - There's no `GLOSSARY.md` or `docs/adr/` yet, so I'll create them when the first term or ADR is settled.
> 
> **Already decided (I won't reopen these):**
> - Event-sourced log: you chose it over an audit table and CDC because auditors must be able to replay any order's history.
> - Postgres: it's the only database you run, so nothing else was considered.
> - "Export" → "Download CSV": a label change only.
> 
> ❓ **Q1** - **ADR for event sourcing**: Decision 1 meets all three ADR tests: it's hard to reverse (every read model would need rebuilding), a future reader would wonder why, and you rejected real alternatives (audit table, CDC). Decisions 2 and 3 don't qualify: Postgres had no alternative, and a label is easy to change back.
> 
> ➡️ Write `docs/adr/0001-event-sourced-order-storage.md` and list the audit table and CDC under Considered Options.
> 
> ---
> 
> ❓ **Q2** - **What "replay" means for auditors**: Auditors might need (a) the ordered list of events for an order, (b) the order's state as of any point in time, or (c) both. This decides the audit tooling and the glossary term.
> 
> ➡️ Both: the event list, plus an as-of view of the order's state at any timestamp.
> 
> ---
> 
> ❓ **Q3** - **Orders that exist before cutover**: CRUD rows have no history to replay. Options: (a) one `OrderMigrated` event per order holding its current state, so history starts at cutover; (b) rebuild partial history from whatever logs or timestamps exist; (c) leave old orders in CRUD tables, which are then frozen.
> 
> ➡️ (a), and you confirm with the auditors that history before cutover isn't replayable.
> 
> ---
> 
> ❓ **Q4** - **Event store shape in Postgres**: Options: (a) one append-only `events` table with a unique `(stream_id, version)` for optimistic concurrency; (b) a table per event type; (c) an extension or library such as Marten-style or pg-eventstore.
> 
> ➡️ (a), with UPDATE and DELETE revoked on that table so it really is append-only.
> 
> ---
> 
> ❓ **Q5** - **Read model consistency**: Options: (a) projections update in the same transaction as the event append, so reads are strongly consistent; (b) an async projector, so reads are eventually consistent.
> 
> ➡️ (a) for the orders page read model; move to (b) only if write latency becomes a problem.
> 
> ---
> 
> ❓ **Q6** - **Personal data in an immutable log**: Erasure requests clash with "replay full history". Options: (a) keep personal data out of events and reference the customer by ID; (b) crypto-shredding, with per-customer keys you destroy on erasure; (c) accept that events can't be erased.
> 
> ➡️ (a): events carry `customer_id` only, and personal data stays in a mutable customer record.
> 
> ---
> 
> ❓ **Q7** - **Event schema evolution**: Stored events never change, but their shapes will. Options: (a) versioned event types plus upcasters that convert old versions when read; (b) rewriting old events in a migration.
> 
> ➡️ (a), because rewriting events would undermine the audit guarantee that justified the whole rework.
> 
> ---
> 
> ❓ **Q8** - **What "Download CSV" contains**: The label is settled. Open: do the columns and rows stay exactly as they are now, served from the new orders read model?
> 
> ➡️ Yes: same columns and same rows, read from the read model, and only the label changes.

Votes:

- adr-only-when-all-three: PASS PASS PASS (passed)
- no-adr-for-trivial-decisions: PASS (passed)

### with, run 5

Reply:

> Understood: event sourcing, the existing Postgres cluster and the "Download CSV" label are settled, and you want me to grill you on the rest of the order service rework.
> 
> I logged the one decision that needs an ADR and found 8 open decisions to ask about this round.
> 
> - **Event sourcing**: I recorded it in `docs/adr/0001-event-sourced-order-storage.md`.
>   - It is hard to reverse, a future reader would ask why, and you weighed it against two other options.
>   - The ADR lists the audit table and change data capture as rejected without reasons, because you didn't give any. Tell me if you want them added.
> - **Postgres**: no ADR, because there was no other option on the table.
> - **"Download CSV" label**: no ADR, because it's easy to change back.
> - **No code to check against**: the repo has only `CLAUDE.md`. The `docs/agents/*.md` files it points to don't exist, so I couldn't check anything you say against code.
> 
> ❓ **Q1** - **Stream boundary**: Is each order its own event stream (one aggregate per order), or do some events span several orders, such as split shipments or merged carts?
> 
> ➡️ One stream per order; anything that spans orders becomes separate events in each order's stream.
> 
> ---
> 
> ❓ **Q2** - **Orders that already exist**: The log can't contain history the CRUD tables never kept. Options:
> - (a) Seed each order with a single `OrderImported` snapshot event.
> - (b) Rebuild events from whatever timestamps and fields you have.
> - (c) Leave old orders in CRUD.
> 
> ➡️ (a), and you tell auditors in writing that history before the cutover date is a snapshot only.
> 
> ---
> 
> ❓ **Q3** - **Event store mechanics**: Do you write your own append-only `events` table, with stream id, a version number with a unique constraint, and a JSONB payload? Or do you use a library for your stack? What language is the order service in?
> 
> ➡️ Write your own table, with optimistic concurrency on `(stream_id, version)`, unless your stack has a mature Postgres event-store library.
> 
> ---
> 
> ❓ **Q4** - **Read model consistency**: Are projections updated in the same transaction as the event append (consistent at once), or asynchronously (eventually consistent)?
> 
> ➡️ Update the orders-page read model in the same transaction; any other read models update asynchronously.
> 
> ---
> 
> ❓ **Q5** - **Personal data in an immutable log**: When a customer asks to be erased, how do you remove them from events that can't change? Options:
> - (a) Crypto-shredding: encrypt personal data with a per-customer key, then delete the key.
> - (b) Store only a customer ID in events and keep personal data outside the log.
> 
> ➡️ (b). Events hold only the customer ID, and order events don't carry names or addresses.
> 
> ---
> 
> ❓ **Q6** - **Cutover**: Options:
> - (a) Big-bang switch during a maintenance window.
> - (b) Dual-write to CRUD and the log for a while, then compare the two and switch reads over.
> 
> ➡️ (b), with a set comparison period, then the CRUD writes are removed.
> 
> ---
> 
> ❓ **Q7** - **What auditors get from "replay"**: Options:
> - (a) The raw ordered list of events.
> - (b) The order's state at any chosen point in time.
> - (c) Both.
> 
> Is it an internal tool, an export, or direct database access?
> 
> ➡️ (c), through an internal read-only screen: events listed in time order, plus "state as of" a chosen timestamp.
> 
> ---
> 
> ❓ **Q8** - **What "Download CSV" contains**: Does it keep today's export exactly (the current state of each order, from the read model), or change too, for example by adding event history?
> 
> ➡️ Keep the contents exactly as today; only the label changes.

Votes:

- adr-only-when-all-three: PASS PASS PASS (passed)
- no-adr-for-trivial-decisions: PASS (passed)

## grill-small-feature

### with, run 1

Reply:

> Understood: you want a button on the admin app's orders page that downloads the orders currently shown as a CSV file, and you want the idea grilled until it's fully specified.
> 
> I checked the workspace first, and the answers will have to come from you.
> 
> - The working directory has no app code that mentions orders, CSV or export.
> - There is no `GLOSSARY.md`, `GLOSSARY-MAP.md` or `docs/` yet.
> - I'll create `GLOSSARY.md` once the first term is settled. The first candidate is what "orders currently shown" means.
> 
> These are the decisions open now. Each recommendation is worded so that "yes" accepts it.
> 
> ❓ **Q1** - **What "currently shown" means**: (a) only the rows on the current page, or (b) every order that matches the current filters, search and sort, across all pages.
> 
> ➡️ (b), every order matching the current filters. A user who exports page 1 of 40 almost never wants just those 25 rows. I'd name this set the **Filtered Order Set** in the glossary.
> 
> ---
> 
> ❓ **Q2** - **Which columns go in the file**: (a) exactly the columns the table shows, or (b) a fixed export field set that can include fields the table hides (customer email, line items, totals broken down).
> 
> ➡️ (a), the table's visible columns, in the same order. The file then matches the screen, and we avoid deciding a second field set now.
> 
> ---
> 
> ❓ **Q3** - **Who can export**: (a) any staff member who can see the orders page, or (b) only staff with a separate export permission.
> 
> ➡️ (b), a separate permission. A file of orders with customer details leaves the app's access controls once it's downloaded, so seeing orders and taking them home are different privileges.
> 
> ---
> 
> ❓ **Q4** - **Audit trail**: should each export be logged (who, when, which filters, how many rows)?
> 
> ➡️ Yes, log every export. It's cheap, and it's the only record once the data is on someone's laptop.
> 
> ---
> 
> ❓ **Q5** - **Who opens the file**: mainly Excel users, which means a UTF-8 BOM, locale-safe dates and numbers that don't get mangled, or mainly scripts and other tools that want plain RFC 4180 UTF-8.
> 
> ➡️ Excel-friendly. Staff in an admin app will almost certainly double-click the file. ISO 8601 dates keep it parseable by scripts too.

Votes:

- numbered-with-recommendations: PASS (passed)
- whole-frontier: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: you want a button on the admin app's orders page that lets staff download a CSV of the orders they're currently looking at, and you want me to question the idea before anything gets built.
> 
> Round 1 covers the decisions that everything else depends on.
> 
> - The repo has only `CLAUDE.md`, so there is no orders page code or `GLOSSARY.md` for me to check your description against.
> - The `docs/agents/*` files that `CLAUDE.md` points to don't exist yet.
> - Because of that, I'm treating everything you tell me about current behaviour as a fact I can't verify.
> 
> ❓ **Q1** - **What "currently shown" means**: (a) only the rows on the current page, (b) every order that matches the current filters, search and sort, across all pages, or (c) every order, ignoring filters.
> 
> ➡️ (b): staff export to get the whole filtered set, and a page-only export quietly leaves rows out.
> 
> ---
> 
> ❓ **Q2** - **Columns**: (a) the same columns the table shows, in the same order, or (b) a fixed export layout that can include fields the table hides, such as line items or customer email.
> 
> ➡️ (a): it matches what staff see, and nobody has to design a separate layout.
> 
> ---
> 
> ❓ **Q3** - **Who can export**: (a) anyone who can see the orders page, or (b) only a specific role or permission, because a file holding customer data can leave the building.
> 
> ➡️ (a) for now, unless the orders contain personal or payment data your policy restricts.
> 
> ---
> 
> ❓ **Q4** - **Audit trail**: should each export be logged with who ran it, when, which filters were applied and how many rows came out?
> 
> ➡️ Yes: it's cheap, and it answers "who took this data?" if that question ever comes up.
> 
> ---
> 
> ❓ **Q5** - **Who opens the file**: (a) mostly Excel, (b) mostly other tools or scripts, or (c) both.
> 
> ➡️ (a): plan for Excel, which means UTF-8 with a BOM, ISO dates and plain numbers for money with no currency symbol.

Votes:

- numbered-with-recommendations: PASS (passed)
- whole-frontier: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: you want to stress-test a CSV export button on the admin orders page before anything gets built. I'm only writing glossary entries and ADRs during this.
> 
> Here is round 1, the questions that don't depend on any other open decision.
> 
> - The workspace has only `CLAUDE.md`, with no app code, `GLOSSARY.md` or `docs/agents/domain.md`.
> - So I can't check any of this against the code, and these are your calls.
> - "Orders currently shown" is the fuzziest phrase here, so it comes first.
> 
> ❓ **Q1** - **What "currently shown" means**: (a) only the rows on the current page; (b) every order that matches the current filters, search and sort, across all pages; (c) every order, ignoring filters.
> 
> ➡️ (b): staff usually filter first and expect the whole result, not just page 1 of it.
> 
> ---
> 
> ❓ **Q2** - **Which columns**: (a) the same columns the table shows; (b) a fixed, wider export layout (IDs, customer, totals, status, timestamps, and so on).
> 
> ➡️ (b): a fixed layout keeps files consistent for whatever reads them later, like spreadsheets or finance imports.
> 
> ---
> 
> ❓ **Q3** - **What one row is**: (a) one row per order; (b) one row per line item, with order fields repeated.
> 
> ➡️ (a): it matches what the page lists, and line items can be a separate export later.
> 
> ---
> 
> ❓ **Q4** - **Who can export**: (a) anyone who can see the orders page; (b) only staff with a separate export permission.
> 
> ➡️ (b): a CSV takes customer personal data off the system in bulk, so it should be a deliberate grant.
> 
> ---
> 
> ❓ **Q5** - **Audit trail**: should each export be logged with who ran it, when, which filters and how many rows?
> 
> ➡️ Yes: it's cheap, and it answers "who pulled this data?" after a leak.
> 
> ---
> 
> ❓ **Q6** - **Main consumer**: who opens the file? (a) people in Excel; (b) other tools or scripts; (c) both.
> 
> ➡️ (a) Excel: that settles encoding (UTF-8 with BOM), date format and how money is written, and I'll ask about those next round.

Votes:

- numbered-with-recommendations: PASS (passed)
- whole-frontier: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: you want to settle the design of a CSV export button on the admin orders page before anything gets built.
> 
> There's no code to check against yet, so round 1 is the decisions that don't depend on anything else.
> 
> - The repo holds only `CLAUDE.md`.
> - No orders page, no `GLOSSARY.md` and no `docs/agents/*.md` files exist, even though `CLAUDE.md` refers to them.
> - So I can't check how the orders page filters, sorts or pages its results, and these questions ask you instead.
> - "Orders currently shown" is the vaguest term so far, so Q1 pins it down.
> 
> ❓ **Q1** - **What "currently shown" means**: (a) only the rows on the current page, or (b) every order that matches the current filters and sort order, across all pages.
> 
> ➡️ Yes to (b): staff almost always want "everything matching my filter", and an export of only page 1 tends to get reported as a bug.
> 
> ---
> 
> ❓ **Q2** - **Row grain**: (a) one row per order, or (b) one row per line item, with the order fields repeated on each row.
> 
> ➡️ Yes to (a), one row per order, to match what the orders page lists.
> 
> ---
> 
> ❓ **Q3** - **Columns**: (a) the same columns the table shows, or (b) a fixed export layout that can include fields the table doesn't show.
> 
> ➡️ Yes to (a), mirror the visible table columns, so the file matches what staff see on screen.
> 
> ---
> 
> ❓ **Q4** - **Who can export**: (a) anyone who can open the orders page, or (b) only staff with a separate export permission, because a bulk file of customer data leaves the app.
> 
> ➡️ Yes to (b), a separate export permission, because one CSV can hold every customer's details. This is my best guess; only you know your data policy.
> 
> ---
> 
> ❓ **Q5** - **Audit trail**: should each export be logged, with who ran it, when, which filters were used and how many rows came out?
> 
> ➡️ Yes, log every export, since that's cheap now and hard to add after a data-leak question comes up.

Votes:

- numbered-with-recommendations: PASS (passed)
- whole-frontier: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: you want to stress-test a CSV export button on the admin orders page before anything gets specced.
> 
> I checked the repo and there's nothing to compare your plan against, so these questions start from your description.
> 
> - The working directory has no app code, no `GLOSSARY.md` and no `docs/`.
> - So I can't check how the orders page filters, sorts or paginates today. Correct me where my guesses are wrong.
> - These questions don't depend on each other. File size, sync vs. async, and naming come in a later round.
> 
> ❓ **Q1** - **Which orders does "currently shown" mean?**: only the rows on the current page, or every order that matches the current filters and sort, across all pages?
> 
> ➡️ Every order matching the current filters and sort, across all pages. Staff almost always want the whole filtered set, not just page 1.
> 
> ---
> 
> ❓ **Q2** - **One row per what?**: one row per order, or one row per line item with the order fields repeated on each row?
> 
> ➡️ One row per order. Per-line-item can be a separate export later if someone asks for it.
> 
> ---
> 
> ❓ **Q3** - **Which columns?**: the same columns as the on-screen table, or a fixed export layout that may have more fields (customer email, address, internal IDs)?
> 
> ➡️ A fixed export layout that you define. A file read by spreadsheets and scripts shouldn't change shape whenever someone tweaks the table's UI.
> 
> ---
> 
> ❓ **Q4** - **Who can export?**: anyone who can see the orders page, or only staff with a separate export permission? A CSV takes customer data out of the app, which matters more if the columns include PII.
> 
> ➡️ A separate export permission, granted to the current orders-page staff by default.
> 
> ---
> 
> ❓ **Q5** - **Audit trail**: record each export (who, when, which filters, row count), or don't record exports?
> 
> ➡️ Yes, record each one. It costs little and answers "who downloaded our customer list?" later.
> 
> ---
> 
> ❓ **Q6** - **Who opens the file?**: mainly Excel/Google Sheets users or scripts and imports? This decides encoding (a UTF-8 marker so Excel shows accents correctly), date format and whether amounts include currency symbols.
> 
> ➡️ Excel/Sheets users first: UTF-8 with the marker, ISO dates (`2026-11-12`), plain numbers for amounts and a separate currency column.

Votes:

- numbered-with-recommendations: PASS (passed)
- whole-frontier: PASS PASS PASS (passed)

## grill-term-clash

### with, run 1

Reply:

> Understood: you mean one delivered Line Item that the customer sends back and gets refunded for, and you've left the name to me.
> 
> I've named it **Return** and added it to `GLOSSARY.md`, with "item cancellation" and "cancel" on its _Avoid_ list.
> 
> - The name clashes with the glossary: it defines **Cancellation** as withdrawing a whole Order before Dispatch, with nothing sent and nothing charged.
> - Your "cancel an item" happens after delivery, covers one Line Item and involves a refund, so it's a different concept.
> - I picked "Return" because it's the word customers and support staff already use for sending an item back.
> - I haven't written an ADR because a name is cheap to change later.
> 
> ❓ **Q1** - **Quantity**: a Line Item has a quantity (say 3 mugs). Does a Return always cover the whole Line Item, or can the customer return just some of it (1 of 3)?
> 
> ➡️ A Return always covers the whole Line Item and its full quantity, matching your definition.
> 
> ---
> 
> ❓ **Q2** - **Delivery as a term**: the glossary only has Dispatch, but a Return can only start once the item has arrived. Should I add **Delivery** as "the moment an Order reaches the customer", and use it as the starting point for returns?
> 
> ➡️ Yes, add Delivery, based on the carrier's delivered status.
> 
> ---
> 
> ❓ **Q3** - **Return window**: how long after Delivery can a customer start a Return? Options: 14 days, 30 days, or no limit.
> 
> ➡️ 30 days after Delivery.
> 
> ---
> 
> ❓ **Q4** - **When the refund is paid**: when the customer starts the Return, or when the shop receives the item?
> 
> ➡️ When the shop receives the item.
> 
> ---
> 
> ❓ **Q5** - **Refund amount**: the Line Item's price exactly, or the price paid after its share of any order-level discount? Is the original shipping refunded?
> 
> ➡️ Refund the price actually paid, including its share of any order discount; don't refund the original shipping.
> 
> ---
> 
> ❓ **Q6** - **Return shipping cost**: does the shop send a free prepaid label, or does the customer pay to send it back?
> 
> ➡️ The shop sends a free prepaid label.
> 
> ---
> 
> ❓ **Q7** - **Several Returns per Order**: can a customer return more than one Line Item from the same Order, each as its own Return?
> 
> ➡️ Yes; each Line Item gets its own Return, and they can run at the same time.
> 
> ---
> 
> ❓ **Q8** - **Non-returnable products**: are some products excluded from returns (hygiene, perishable or personalised items)?
> 
> ➡️ Yes; mark products as returnable or not, with returnable as the default.
> 
> ---
> 
> ❓ **Q9** - **Return reason**: should the customer have to give a reason?
> 
> ➡️ Yes, picked from a fixed list; the reason only feeds reporting and doesn't change the refund.
> 
> ---
> 
> ❓ **Q10** - **Refund destination**: the original payment method, or store credit?
> 
> ➡️ The original payment method only.
> 
> ---
> 
> ❓ **Q11** - **Item never arrives back**: if a Return is started but the item never reaches the shop, what happens?
> 
> ➡️ The Return expires 30 days after it was started, with no refund, and the Line Item can't be returned again.
> 
> What happens when a returned item arrives damaged or isn't the right item depends on Q4, so I'll ask about it in the next round.

Votes:

- clash-called-out: PASS PASS PASS (passed)
- glossary-written-inline: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: you want one delivered Line Item sent back and refunded on its own, and you've left the name to me.
> 
> I named it **Return**, added it to `GLOSSARY.md`, and the next round of questions is below.
> 
> - The name clashes with the glossary: there, **Cancellation** means withdrawing a whole Order before Dispatch, with nothing sent and nothing charged.
> - Your "cancel an item" happens after delivery, covers one Line Item, and involves a charge being reversed, so calling it Cancellation would blur two concepts.
> - I picked **Return** as the canonical term.
> - "Item cancellation", "partial cancellation" and "cancel an item" are now listed under _Avoid_.
> - Cancellation keeps its current meaning.
> 
> ❓ **Q1** - **Quantity within a Line Item**: A Line Item can have quantity > 1 (e.g. 3 × mug). Does a Return always take back the whole Line Item, or can it take back part of the quantity (1 of 3 mugs)?
> 
> ➡️ A Return can cover any quantity up to what was delivered, and the refund is prorated per unit.
> 
> ---
> 
> ❓ **Q2** - **Defining "arrived"**: The glossary has Dispatch but no term for arrival. Should I add **Delivery** ("the moment an Order reaches the customer, as recorded by the carrier") as the event that makes a Return possible?
> 
> ➡️ Yes, add Delivery, with carrier confirmation as the source of truth.
> 
> ---
> 
> ❓ **Q3** - **Return window**: Is there a deadline after Delivery for starting a Return?
> 
> ➡️ 30 days from Delivery.
> 
> ---
> 
> ❓ **Q4** - **Eligibility**: Can every product be returned, or are some excluded (e.g. perishables, personalised goods, hygiene items)?
> 
> ➡️ Everything can be returned unless the product is flagged as non-returnable.
> 
> ---
> 
> ❓ **Q5** - **When the refund happens**: Is the refund issued when the customer requests the Return, when the carrier picks it up, or when the warehouse receives it?
> 
> ➡️ When the warehouse receives it.
> 
> ---
> 
> ❓ **Q6** - **Refund amount**: Is the refund the Line Item's list price, or the price actually paid (after its share of any order-level discount)? Is the original shipping charge refunded?
> 
> ➡️ The price actually paid, including its prorated share of discounts, with no shipping refunded.
> 
> ---
> 
> ❓ **Q7** - **Return shipping cost**: Who pays to send the item back?
> 
> ➡️ The shop provides a prepaid label and the customer pays nothing.
> 
> ---
> 
> ❓ **Q8** - **Several Returns per Order**: Can a customer make several Returns on the same Order, e.g. two different Line Items, or the same Line Item twice in separate parts?
> 
> ➡️ Yes, each Return is independent, but the total returned can never exceed the quantity delivered.

Votes:

- clash-called-out: PASS PASS PASS (passed)
- glossary-written-inline: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: a customer sends back one delivered line item and gets a refund for that item only; you've left the naming to me.
> 
> I named it **Return** and added it to `GLOSSARY.md` along with **Refund**.
> 
> - Your glossary defines **Cancellation** as withdrawing a *whole Order before Dispatch*, so "cancel an item" would clash with it.
> - I picked **Return** because the item has already arrived and physically comes back.
> - "Cancel an item", "item cancellation" and "partial cancellation" are now listed under _Avoid_.
> - **Refund** is defined as money paid back for a Returned Line Item.
> - The repo has no code yet, only `CLAUDE.md` and `GLOSSARY.md`, so there was nothing to check your description against.
> - I didn't write an ADR, because this name is cheap to change later.
> 
> ❓ **Q1** - **Partial quantity**: A Line Item has a quantity, for example 3 × socks. Can a Return cover only some of those units, or must the whole Line Item come back?
> 
> ➡️ Whole Line Item only, matching your "one line item comes back".
> 
> ---
> 
> ❓ **Q2** - **Return window**: How long after delivery can a Customer start a Return?
> 
> ➡️ 30 days from delivery.
> 
> ---
> 
> ❓ **Q3** - **Refund trigger**: When is the Refund issued: when the Return is requested, when the carrier scans the parcel, or when the warehouse receives it?
> 
> ➡️ When the warehouse receives it.
> 
> ---
> 
> ❓ **Q4** - **Refund amount**: Is it the Line Item's list price, or what the Customer actually paid (after the Order's discounts are shared out across items)? Is any original shipping refunded?
> 
> ➡️ What the Customer actually paid for that Line Item, with no shipping refund.
> 
> ---
> 
> ❓ **Q5** - **Return shipping cost**: Who pays to send the item back: the shop (prepaid label) or the Customer?
> 
> ➡️ The shop provides a free prepaid label.
> 
> ---
> 
> ❓ **Q6** - **Eligibility**: Can some products never be returned (hygiene items, personalised goods, final-sale items)?
> 
> ➡️ Every product can be returned for now; non-returnable products wait for later.
> 
> ---
> 
> ❓ **Q7** - **Multiple Returns per Order**: Can a Customer return several Line Items from one Order, each as its own Return, at different times?
> 
> ➡️ Yes: one Return per Line Item, any number per Order, each one inside the window.
> 
> ---
> 
> ❓ **Q8** - **Return reason**: Must the Customer give a reason, and does the reason change anything (for example, who pays shipping)?
> 
> ➡️ A reason is required, chosen from a fixed list, and it's only recorded; it doesn't change eligibility or cost.
> 
> ---
> 
> ❓ **Q9** - **Refund destination**: Does the Refund go to the original payment method, or can it be store credit?
> 
> ➡️ Original payment method only.

Votes:

- clash-called-out: PASS PASS PASS (passed)
- glossary-written-inline: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: you want one delivered Line Item sent back and refunded on its own, and you've left the naming to me.
> 
> I've named it **Return**, added it to `GLOSSARY.md`, and below is the first round of questions.
> 
> - **Naming clash:** the glossary already uses **Cancellation** for withdrawing a whole Order before Dispatch, with nothing sent and nothing charged.
> - Your "cancel an item" happens after delivery, covers one Line Item, and involves a refund, so it's a different thing.
> - Calling it a cancellation would give that word two meanings.
> - **Name chosen:** **Return**, because it's the word customers and the shop already use for this.
> - "Item cancellation", "cancel an item" and "partial cancellation" are listed under `_Avoid_`.
> - **Code:** the repo has no code yet, so I had nothing to check your description against.
> 
> ❓ **Q1** - **Quantity**: a Line Item is one product plus a quantity. If a Line Item has 3 units, does a Return take back all 3, or can it take back fewer?
> 
> ➡️ Let a Return cover any number of units from 1 up to the Line Item's quantity. "I only want to send back one of the three" is the usual case.
> 
> ---
> 
> ❓ **Q2** - **Delivery**: the glossary records Dispatch but not arrival. What makes a Line Item count as delivered?
> 
> ➡️ Add **Delivery** as its own event, taken from the carrier's delivered confirmation. A Return is only allowed after it.
> 
> ---
> 
> ❓ **Q3** - **Return window**: how long after Delivery can a customer start a Return?
> 
> ➡️ 30 days from Delivery, with the same window for all products.
> 
> ---
> 
> ❓ **Q4** - **Non-returnable products**: are some products excluded, such as perishables, hygiene items or personalised goods?
> 
> ➡️ Yes. Mark each product as returnable or not. Products are returnable unless marked otherwise.
> 
> ---
> 
> ❓ **Q5** - **When the refund happens**: options are (a) when the customer asks, (b) when the warehouse receives the item, or (c) after the warehouse checks the item's condition.
> 
> ➡️ (b) when the warehouse receives it. Condition checks and rejected returns come next round if you want them.
> 
> ---
> 
> ❓ **Q6** - **Refund amount**: the item price only, or also a share of order-level discounts and the original shipping cost?
> 
> ➡️ Refund what the customer actually paid for those units. That's the item price minus their share of any order discount. Original shipping is not refunded.
> 
> ---
> 
> ❓ **Q7** - **Return shipping cost**: who pays to send the item back?
> 
> ➡️ The customer pays, unless the item arrived faulty or wrong. Then the shop pays.
> 
> ---
> 
> ❓ **Q8** - **More than one Return per Order**: can a customer return several Line Items from the same Order, at different times?
> 
> ➡️ Yes. Each Return covers exactly one Line Item, and an Order can have as many Returns as it has eligible Line Items.
> 
> ---
> 
> ❓ **Q9** - **Who starts a Return**: the customer from their account, support staff on the customer's behalf, or both?
> 
> ➡️ Both. They follow the same rules, and support staff can't get around the return window.

Votes:

- clash-called-out: PASS PASS PASS (passed)
- glossary-written-inline: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: one delivered Line Item is sent back and refunded on its own, and you've left the name to me.
> 
> I named it **Return**, added it to `GLOSSARY.md`, and the first round of questions is below.
> 
> - Your glossary already defines **Cancellation** as withdrawing a whole Order before Dispatch.
> - Calling the new flow "cancel an item" would clash with that, so the glossary now lists "item cancellation" and "cancel item" as terms to avoid.
> - I chose **Return** because it's the word customers already use for sending something back after it arrives.
> - The repo has no code, so I had nothing to check your description against.
> 
> ❓ **Q1** - **Partial quantity**: A Line Item can hold several units, for example 3 mugs. Can the customer send back only some of them (say 1 of the 3), or only the whole Line Item?
> 
> ➡️ A Return covers some or all units of one Line Item, and the refund is per unit returned.
> 
> ---
> 
> ❓ **Q2** - **Return window**: How long after delivery can a customer start a Return? Choices are a fixed number of days, a window per product, or no limit.
> 
> ➡️ 30 days from delivery, the same for every product.
> 
> ---
> 
> ❓ **Q3** - **What "delivered" means**: The glossary only goes as far as Dispatch, so nothing defines when an item counts as delivered. Is that the carrier's delivery confirmation, the customer saying it arrived, or a fixed number of days after Dispatch?
> 
> ➡️ The carrier's delivery confirmation; I'd add it to the glossary as **Delivery**.
> 
> ---
> 
> ❓ **Q4** - **When the refund is paid**: Is the refund paid as soon as the customer starts the Return, when the carrier scans the parcel, or when the warehouse receives and checks the item?
> 
> ➡️ When the warehouse receives and checks the item.
> 
> ---
> 
> ❓ **Q5** - **Refund amount**: Order-wide discounts and the original shipping charge both touch this Line Item. Does the refund include a share of either?
> 
> ➡️ Refund what was actually paid for the returned units, minus their share of any order discount, and don't refund the original shipping.
> 
> ---
> 
> ❓ **Q6** - **Who pays return shipping**: Does the shop pay, does the customer pay, or does it depend on the reason (for example, faulty versus changed mind)?
> 
> ➡️ The shop pays when the item is faulty or wrong, and the customer pays otherwise.
> 
> ---
> 
> ❓ **Q7** - **Which products can be returned**: Can every product be returned, or are some never returnable (for example, perishables or hygiene products)?
> 
> ➡️ Each product has a returnable flag, and it's on by default.
> 
> ---
> 
> ❓ **Q8** - **Several Returns on one Order**: Can a customer return several Line Items from the same Order, each as its own Return, with more than one in progress at a time?
> 
> ➡️ Yes; each Line Item gets its own Return, and several can be open on one Order at once.
> 
> ---
> 
> ❓ **Q9** - **Where the refund goes**: Does the money go back to the original payment method, to store credit, or does the customer choose?
> 
> ➡️ Back to the original payment method only.

Votes:

- clash-called-out: PASS PASS PASS (passed)
- glossary-written-inline: PASS PASS PASS (passed)
