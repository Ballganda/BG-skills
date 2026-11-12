// Stub for `claude -p` in the regrade test: logs the prompt and arguments,
// answers from STUB_VERDICTS (comma list, cycled), reports STUB_COST.
import { appendFileSync, readFileSync, existsSync, writeFileSync } from "node:fs";

const prompt = readFileSync(0, "utf8");
const log = process.env.STUB_LOG;
appendFileSync(log, JSON.stringify({ prompt, args: process.argv.slice(2) }) + "\n");
const counter = log + ".n";
const n = existsSync(counter) ? Number(readFileSync(counter, "utf8")) : 0;
writeFileSync(counter, String(n + 1));
const verdicts = (process.env.STUB_VERDICTS ?? "PASS").split(",");
const v = verdicts[n % verdicts.length];
const result = /exactly one word/.test(prompt)
  ? v
  : `item 1 is one fact.\nitem 2 is one fact.\nVERDICT: ${v}`;
process.stdout.write(JSON.stringify({ type: "result", is_error: false, result, total_cost_usd: Number(process.env.STUB_COST ?? 0) }));
