# Kept Replies and grader votes

## reply-three-decisions

### with, run 1

Reply:

> Understood: you want a date-formatting function exported from `utils.js`, and I should only ask questions for now, without editing or running anything.
> 
> I need four decisions from you before I build it. You can answer by number, and "yes" accepts my recommendation.
> 
> 1. **Output format.** I recommend ISO date only, `YYYY-MM-DD` (e.g. `2026-11-12`).
>    - It sorts correctly and is the same in every environment.
>    - Other options: something readable like `Nov 12, 2026`, or a format string the caller passes in.
> 2. **Locale argument.** I recommend no locale argument for now.
>    - A fixed ISO format doesn't need one.
>    - If you pick a readable format instead, I'd add an optional `locale` argument that defaults to `'en-US'` and uses `Intl.DateTimeFormat`.
> 3. **Invalid input.** I recommend throwing a `TypeError`.
>    - Bad dates fail loudly instead of showing up as blank text.
>    - Returning `''` is safer if the output goes straight into UI templates.
> 4. **Accepted input types.** I recommend accepting a `Date`, a timestamp number or a date string.
>    - Every input is turned into a `Date` before formatting.
>    - Anything that turns into `Invalid Date` counts as invalid input.
> 5. **Name and export style.** I recommend `formatDate`, exported the same way `utils.js` already exports things.
>    - I haven't opened `utils.js` yet, so I don't know if it uses ESM or CommonJS.
> 6. **Tests.** I recommend writing a few unit tests alongside it, test-first.
>    - The tests would cover valid input, invalid input and the edge cases from your answers above.

Votes:

- numbered-with-recommendation: PASS PASS PASS (passed)
