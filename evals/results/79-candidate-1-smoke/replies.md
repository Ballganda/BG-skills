# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> I made both changes in `utils.js`. As you asked, I didn't run anything, so neither change has been tested.
> 
> **Changes:**
> - **`slugify`** now has `.replace(/-+/g, "-")` added after the step that turns spaces into dashes. Runs of dashes become a single dash, whether they came from the input or from that step. For example, `"a -- b"` gives `"a-b"`.
> - **`titleCase(s)`** is new and exported next to `slugify`. It capitalises the first character after the start of the string or after any whitespace, and leaves everything else as it is.
>   - I split words on whitespace instead of using `\b\w`. With `\b\w`, `"don't"` would come out as `"Don'T"`.
>   - Letters that are already capitals stay that way: `"hello WORLD"` gives `"Hello WORLD"`. Say if you'd rather the rest of each word be lowercased.
> 
> **Not handled:**
> - `slugify` still keeps leading or trailing dashes (for example `"-foo-"`) and punctuation. You only asked for the collapsing, so I left the rest alone.
> - I found no tests in the repo and didn't add any.
> - Nothing is committed. The git status shows the whole directory as untracked.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### without, run 1

Reply:

> I've made both changes in `utils.js`. As you asked, I didn't run anything, so the code is untested.
> 
> **What changed:**
> - **`slugify`** now ends with `.replace(/-+/g, "-")`, so repeated dashes collapse into one. That covers dashes already in the input (`"a--b"` → `"a-b"`) and ones created by replacing spaces (`"a - b"` → `"a-b"`).
> - **`titleCase(s)`** is new and exported next to `slugify`. It capitalises the first letter of each word, where a word is anything that starts the string or follows whitespace. The rest of each word is left alone, so `"hello wORLD"` → `"Hello WORLD"`.
> 
> **Things to be aware of:**
> - `titleCase` doesn't lowercase the rest of each word. If you want `"hELLO"` → `"Hello"`, that's a one-line change.
> - Hyphenated words only get their first letter capitalised: `"well-known"` → `"Well-known"`.
> - `slugify` still keeps leading or trailing dashes from the input (`"-foo-"` stays `"-foo-"`). It also doesn't remove punctuation, which is the same as before.
> - There are no tests in the repo for either function, so nothing checks this behaviour yet.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)
