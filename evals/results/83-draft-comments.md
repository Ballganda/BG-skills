# Drafted comments for #78 and #83 (not posted)

Drafted by the ticket #83 implementer. Posting was left to the maintainer.

## For #78

Correction to the finding here. The `reply-context-proof` canary passed because the agent still had Read, Glob and Grep (`allowed_tools: []` does not withhold them) and searched the workspace for the codeword: it found the seeded `CLAUDE.md` with a tool, and the file was not in its context. The eval child runs with `--setting-sources user`, so the project `CLAUDE.md` a scaffold seeds is never loaded. That means the seeded Replies line was not in the agent's context in #72's runs either. Ticket #79 found this (evidence under `evals/results/79-*` on `ticket-79-reword-replies-line`), and #83 fixes it.

## For #83

The context proof now withholds file tools (`disallowed_tools` in its `case.yaml`) and has a second deterministic grader, `seeded-file-not-read`, that fails any run whose trace calls a file-reading tool. The fix: `scripts/eval-grill.sh` stages the cases with `scripts/stage-evals.mjs` into the git-ignored `evals-staged/` and runs the eval with `--eval-dir evals-staged`. Each case whose scaffold seeds a `CLAUDE.md` gets that file's text as `execution.append_system_prompt`. The text comes only from the scaffold, so the Replies line is still taken from the `bg-setup` template. The wording of the Replies line is unchanged.

Proof results, one sample per arm:

| Run | Result | canary-answered | seeded-file-not-read | Cost |
| --- | --- | --- | --- | --- |
| Before the fix (`83-context-proof-before`) | fail, both arms | FAIL | PASS | $0.13 |
| After the fix (`83-context-proof-after`) | pass, both arms | PASS | PASS | $0.13 |

Total eval spend for this ticket: $0.26.

The five-sample rerun of the status-reply case and its control was skipped at the user's request: they asked for no extended comparative testing and no high spend, only a check that the system is valid. That acceptance criterion is still open, and the re-measure of the current wording belongs with the rewording in #79.
