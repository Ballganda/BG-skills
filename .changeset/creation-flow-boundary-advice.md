---
"bg-skills": minor
---

Each creation-flow skill now ends its closing message with one line about the next step: `/grill` says to stay in the session for `/spec-gen`, `/spec-gen` says to clear or start a new chat before `/ticket-gen` if your context is over 150k, and `/ticket-gen` and `/implement` say to always start a new chat before `/implement` and `/code-review`. The skill map's context advice matches, and the skill map and README name `/grill` as where the creation flow starts. A new `npm run check-skills` static check keeps the boundary lines from drifting.
