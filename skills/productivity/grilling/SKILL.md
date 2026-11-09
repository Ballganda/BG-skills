---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map the plan as a **design tree**: each decision branches into the decisions that hang off it.

Work in **rounds**. A round asks the whole **frontier**: every open decision whose prerequisites are settled. A question that depends on another one still open belongs to a later round. Number each question and give each one a recommendation (your best guess when only the user knows), worded so "yes" accepts it. Then wait for the answers:

```
<each decision the user handed you: what you chose and why, one line each>

❓ **Q1** - **<title>**: <the decision and its options, briefly>

➡️ <recommendation, one line>

---

❓ **Q2** - ...
```

Answers push the frontier outward: recompute it and ask the next round.

Facts are yours to find; decisions are the user's. When a question needs a fact from the environment, dispatch a sub-agent with a fresh context window to look it up instead of asking. Only the questions downstream of a running lookup wait; ask the rest now.

Answering a round ("yes", "agree all") settles that round only. The session is done when the frontier is empty: every branch visited, nothing silently assumed. Then ask one closing question on its own, outside any round: have we reached a shared understanding? Take no action until the user answers it.
