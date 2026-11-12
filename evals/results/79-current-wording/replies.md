# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: you want `titleCase` added and exported in `utils.js`, and `slugify` changed so repeated dashes become one, with nothing run.
> 
> I've made both edits in `utils.js`, but neither has been run or tested.
> 
> - `slugify` (`utils.js:1`) now ends with `.replace(/-+/g, "-")`. This also collapses dashes that were already in the input, so `"a -- b"` becomes `"a-b"`.
> - `titleCase` (`utils.js:5`) capitalises the first character after each run of whitespace and at the start of the string. It leaves everything else as it is, so `"hELLO world"` becomes `"HELLO World"`. It does not lowercase the rest of each word.
> - `module.exports` now exports `{ slugify, titleCase }`.
> - `titleCase` only splits words on whitespace, so `"foo-bar"` becomes `"Foo-bar"`.
> - `slugify` still keeps dashes at the start and end (for example, `"-a-"` stays `"-a-"`), because I only changed what you asked for.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js` and make `slugify` collapse repeated dashes, editing files only and running nothing.
> 
> I've made both changes in `utils.js`, but haven't run or tested anything, as you asked.
> 
> - **`slugify`** (`utils.js:2`): I added `.replace(/-+/g, "-")` after the whitespace replacement. Runs of dashes now become one, whether they were in the input or came from spaces next to dashes (e.g. `"a - b"` → `"a-b"`).
> - **`titleCase`** (`utils.js:5-7`): it capitalises the first non-space character after each whitespace or at the start of the string. I didn't use the simpler `\b\w` pattern because it would turn `"don't"` into `"Don'T"`.
> - **What `titleCase` leaves alone:** the rest of each word keeps its case (`"hELLO"` → `"HELLO"`), and words split by hyphens aren't capitalised after the hyphen (`"well-known"` → `"Well-known"`).
> - **Export:** `module.exports` is now `{ slugify, titleCase }`.
> - **Still open:** `slugify` still keeps dashes at the start or end of the string (`"-a-"` stays `"-a-"`), since you didn't ask me to change that. There are no tests in the repo covering either function.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: add and export `titleCase(s)`, make `slugify` collapse repeated dashes, edit only and run nothing.
> 
> Both changes are in `utils.js`. I haven't run or tested anything.
> 
> - **`slugify`** (`utils.js:2`): after turning spaces into dashes, it now merges any run of dashes into one. For example, `"a -- b"` becomes `"a-b"` instead of `"a----b"`.
> - **`titleCase`** (`utils.js:5`): capitalises the first character after the start of the string or after any space. It leaves the rest of each word alone, so `"hELLO"` becomes `"HELLO"`, not `"Hello"`.
> - I avoided the common `\b\w` regex on purpose, because it would turn `"don't"` into `"Don'T"`.
> - **Exports** (`utils.js:9`): `module.exports = { slugify, titleCase }`.
> - **Not handled:** `slugify` still leaves a dash at the start or end if the input already had one (`"-a-"` stays `"-a-"`). It also still keeps punctuation. Neither was part of what you asked for.
> - **Not checked:** I didn't look for other code that calls these functions, and I didn't look for or add tests.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: add and export `titleCase`, make `slugify` collapse repeated dashes, and don't run anything.
> 
> Both changes are made in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` (`utils.js:2`) now ends with `.replace(/-+/g, "-")`, so `"a - b"` and `"a--b"` both become `"a-b"`.
> - `titleCase` (`utils.js:5`) capitalises the first letter after each word boundary and is exported next to `slugify`.
> - `titleCase` leaves the other letters alone, so `"hELLO"` stays `"HELLO"`. If you want the rest lowercased, it needs a `.toLowerCase()` first.
> - Apostrophes count as word boundaries, so `"don't"` becomes `"Don'T"`. Splitting on spaces would fix that if it matters to you.
> - `slugify` doesn't strip leading or trailing dashes (`"-a-"` stays `"-a-"`), and it doesn't remove punctuation. That's the same as before.
> - There are no tests for either function.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes into one, and run nothing.
> 
> Both changes are in `utils.js`, but none of it has been run or tested.
> 
> - `slugify` now collapses runs of dashes into one after it turns whitespace into dashes. For example, `"a - - b"` becomes `"a-b"`, and dashes that were already in the input get collapsed too.
> - `titleCase` capitalises the first non-space character after the start of the string or after whitespace. It leaves the rest of each word alone, so `"hELLO world"` becomes `"HELLO World"` rather than `"Hello World"`.
> - Apostrophes don't start a new word, so `"don't"` becomes `"Don't"`, not `"Don'T"`.
> - `slugify` still keeps a dash at the start or end if the input has one, such as `"-a-"`. I didn't change that because you didn't ask for it.
> - Both functions are exported: `module.exports = { slugify, titleCase }`.
> - There are no tests for either function in the repo.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

## reply-status-no-line

### with, run 1

Reply:

> I made both changes in `utils.js`. As you asked, I didn't run anything, so neither change has been tested.
> 
> **What changed:**
> - **`slugify`** now collapses runs of dashes into one, so `"a - b"` becomes `a-b` instead of `a---b`. This also covers dashes that were already in the input, like `"a--b"`.
> - **`titleCase(s)`** is added and exported next to `slugify`. A "word" is any run of characters that aren't spaces, and only the first letter of each is capitalised. I didn't use the shorter `\b\w` regex because it would turn `"don't"` into `"Don'T"`.
> 
> **Things you might not expect:**
> - `titleCase` leaves the other letters alone: `"hELLO"` becomes `"HELLO"`, not `"Hello"`. If you want the rest of each word lowercased, I can add `.toLowerCase()` first.
> - A word that starts with punctuation isn't capitalised: `"(hello)"` stays as it is.
> - `slugify` still keeps dashes at the start and end, so `" -a- "` gives `-a-`. That was already the behaviour, and I left it alone because you didn't ask to change it.
> 
> I didn't look for other files that use `slugify`, and there are no tests for either function. The dash change could affect anything that relied on the old output.

Votes:

- detail-one-fact-per-line: FAIL (failed)
- outcome-first: FAIL (failed)
