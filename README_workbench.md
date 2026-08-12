# Divmarkup Workbench

A local web GUI replacing the CLI loop in `divmarkup_MAIN.py`. Your existing
modules are used untouched: `MarkupManager`, `tag_substring`,
`selectedSynsetManager`, `LemmaSenseMemory`, `AskClaude`.

## Setup
Put these two items in your project folder, next to your existing modules:

    divmarkup_server.py
    divmarkup_web/index.html
    divmarkup_web/style.css
    divmarkup_web/app.js

One new dependency:

    pip install flask

## Run

    export ANTHROPIC_API_KEY=...        # optional — only for the ✳ toggle
    python divmarkup_server.py path/to/your_text.xml

No path argument → the familiar tkinter file picker. The browser opens to
http://127.0.0.1:5757 automatically. Resume position, per-sentence autosave
(same dated `divmarkup_autosave_session_…xml` convention), and lemma-sense
memory (`lemma_sense_memory.json`) all behave exactly as in the CLI.

## The loop
1. Drag across the sentence to select the apodosis (edges auto-trim whitespace).
2. Words from your span appear as chips — tap to add their senses. Or type a
   word (`/` focuses the box; spellcheck applies, and any correction is shown).
   Senses remembered for a lemma come pre-selected, first sense otherwise.
3. Toggle senses by click or keys 1–9. `synonyms` on a word lists noun
   synonyms as chips.
4. Enter commits: tags the span, autosaves, saves selections to lemma memory.
   If meaningful text remains in the sentence, you stay on it; otherwise you
   land on the next unmarked sentence.

Keys: type to find a span (`:` for to-end mode) · drag to select · Tab cycles
matches / accepts Claude’s ghost · Enter selects, then commits · 1–9 toggle
senses · / add word · Esc clears · ⇧C suggest (when “✳ Claude assists” is on) ·
⇧K next unmarked · ⇧P next partial · ⇧U undo · ⇧W write · ←/→ browse.

The tick strip across the top is the whole document: tall faint ticks are
unmarked, ink ticks are done, cinnabar ticks are partially marked, short pale
ticks are structural lines. Click anywhere on it to jump.

## Gnome marking (span kinds)
Every span can be reviewed as a plain apodosis or a gnome — a freestanding
assertion about the world. Semantics of the `kind` attribute:
no attribute = never reviewed (all pre-existing tags); `kind="prognosis"` =
reviewed, a conditioned prediction (mood: indicative with an explicit or
implied condition); `kind="gnome"` = a freestanding indicative assertion, even
when it instructs by exemplar; `kind="counsel"` = imperative mood. New commits
always carry an explicit kind, chosen via the button row above Commit or the `p`/`g`/`c`
keys. The per-document default comes from the annotation_policy block:
`<annotation_policy default-kind="gnome" …>` (fallback: prognosis when absent
or invalid — a bad value warns at startup). Change texts, change the
attribute; no code edits. To review the back catalog, open a span in the
“Committed in this sentence” panel and tap `prognosis`, `gnome`, or `counsel`; ⇧U undoes a
review like any commit. The vocabulary lives in one constant (`KINDS` in
divmarkup_server.py) if it ever needs to grow — e.g. a `counsel` kind for
advisory apodoses.
⚠ `divmarkup_audit.py` still uses the strict regex and will silently skip
kind-attributed tags; loosen its pattern to
`<(protasis|apodosis) wn_only="(.*?)"(?: kind="(.*?)")?>(.*?)</\1>`
(and unpack four groups) before auditing kinded files.

## Editing a committed span's senses
In the "Committed in this sentence" panel, `edit senses` loads that span's
wn_only list into the senses board — its senses arrive pre-selected under
their words, with sibling senses visible. Edit with all the usual tools
(words, chips, 1–9, synonyms, canon buttons); the span under edit is outlined
in the sentence and the mode bar reads ② EDIT SENSES. Enter saves (rewriting
wn_only in place, preserving the span's kind), Esc cancels, ⇧U undoes a save
like any commit. Synset ids in old tags that WordNet doesn't recognize are
reported and dropped from the board — saving would otherwise silently
re-write them.

## Policy governance at tagging time
If the annotated document contains an `<annotation_policy>` block (see
annotation_policy_draft.xml), the server parses it at startup. Policies with
an `applies="substring, substring"` attribute surface as ⚖ notes in the Senses
pane whenever a selected span contains a trigger — you don't hold the policy
list in your head; the relevant lines find you. `<canon formula="…"
wn_only="…"/>` lines add a one-tap button that applies the canonical senses
when the selected span matches the formula exactly; a typo'd synset id in a
canon line fails loudly, never silently. Routine policy applications are NOT
stamped per-tag — governance is computable from text + policy block, and
hand-stamped provenance makes absence ambiguous. Edit policies in the
document, restart the server to reload them.

## Two behavior changes vs. the CLI (both deliberate)
- **Partially marked sentences are recoverable.** `split_into_sentences`
  flags any line containing markup as `parse=False`, so after a reload the
  CLI skips sentences that still have unmarked text after their last
  `</apodosis>`. The workbench reopens them (they're the cinnabar ticks).
  Your current file has 30 of these.
- **Undo exists** (`u`), one commit at a time, within the running session.

## Known pre-existing quirk (not fixed, just flagged)
`check_spelling` treats any word with *exactly one* noun synset as a possible
misspelling (`len(results) > 1`) and may silently substitute the
spellchecker's idea. In the GUI you'll at least *see* the substitution as a
“word → word” notice, but the `>` arguably should be `>=` in
`divmarkup_wordnet_functions.py` line ~274.

## Security note
`ask_claude.py` (the old module) contains a hardcoded API key. Revoke that key
at console.anthropic.com and delete the file — nothing imports it functionally
(the `ask_claude` name inside `divmarkup_wordnet_functions.py` is the method
parameter, not the module). If you delete it, also remove the vestigial
`import ask_claude` line at the top of `divmarkup_wordnet_functions.py`.
