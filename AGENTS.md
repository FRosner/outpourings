# Writing Guidelines for `outpourings`

This repository contains technical blog posts (`blog_post.md`) along with supporting code, benchmarks, and animations. When drafting or editing prose in this repository, follow the style guidelines below from the start.

## Voice and Tone

- Write in a clear, direct, structured style similar to a strong non-native technical writer: grammatically accurate, plain, and pedagogical, without idiomatic flair or dramatic storytelling.
- Prioritize clarity and precision over punchiness.
- Use "we" when walking the reader through concepts, code, or benchmarks (e.g., "In this post, we will...", "Let's look at..."), and "I" for personal observations.
- Prefer full forms ("does not", "cannot", "we will", "it is") over contractions in explanatory prose. Occasional "let's" is fine.
- Reference posts showing the author's natural voice: `kqueue/blog_post.md` and `rum/blog_post.md`.

## Punctuation and Sentence Structure

- **Do not use em dashes (`—`) or en dashes (`–`).** Use periods, commas, colons, or parentheses instead. Use plain ASCII hyphens (`-`) for ranges (e.g., `2013-2014`, `49.4-51.0 ms`).
- Prefer straightforward Subject-Verb-Object sentences over inverted or rhetorical phrasing (avoid patterns like "At the root of the store sits..." or "Pause and notice what we have built...").
- Break long, multi-clause sentences into two clear sentences rather than chaining thoughts together with dashes or semicolons.

## Avoid LLMisms and Clichés

- Do not open sections with grand aphorisms (e.g., "X are not designed in a vacuum; they are mirrors of..."). State the point directly.
- Avoid overusing "Not X, Y" or "Rather than X, Y" contrast templates.
- Avoid dramatic idioms, editorial buzzwords, and figurative verbs, including phrases like:
  - "rock-solid", "production-grade", "clean-sheet effort", "dead simple", "dead-flat"
  - "left performance on the table", "evaporate in milliseconds", "without missing a beat"
  - "answers our cliffhanger", "live or die by", "makes X unmistakable"
  - "unpack", "rewind to", "hauling", "delve", "landscape", "under the hood" (when overused)
- Avoid staccato rhetorical triplets (e.g., "fast, clean, self-contained").
- Use plain, accurate verbs: "examine", "shows", "overwritten", "exceeds", "explains".

## Structure, Transitions, and Formatting

- Use explicit, straightforward transitions: "First, ...", "Next, ...", "However, ...", "As a result, ...", "Note that ...", "In other words, ...", "Consider ...".
- Introduce code snippets, diagrams, and animations directly (e.g., "The animation below shows...", "Looking at `store/store.go`...").
- Use **bold** sparingly, mainly for list item lead-ins and key terms when first introduced. Avoid bolding arbitrary phrases mid-sentence for emphasis.
- Use *italics* sparingly (e.g., brief parenthetical notes or defined terms), not for conversational stress (avoid italicizing words like *must*, *before*, or *second*).
- Keep backticks for code identifiers, file paths, commands, flags, and exact error messages.

## Quick Check Before Finishing

- Confirm there are zero `—` or `–` characters in the prose.
- Scan headings and opening/closing paragraphs for overly dramatic or promotional phrasing and flatten it into plain technical prose.
- Make sure stylistic edits never drop technical facts, benchmark numbers, source links, or code accuracy.
