# Asking the owner: one question, one card

Every question a worker, a subagent or an agent needs the owner to answer follows this
protocol. It exists because bundled questions get lost: a message that says "two questions:
tab bar placement and browser history" became one board card ("Accept the record?
Sub-questions: …") with one option set, the owner answered that one card, and the worker kept
waiting on answers that never came.

## The rules

1. **One decision per question.** Never put two forks in one question, and never hide a fork
   inside a spec approval ("Accept the record? Sub-questions: …"). A spec approval with open
   points is the approval **plus** one question per open point.
2. **Every question stands alone.** The owner sees it on a card, maybe hours later, next to
   questions from other tickets. Include the ticket key, what is being decided, and enough
   context to answer without opening the record. No "see above", no "as discussed".
3. **Concrete options, recommendation first.** 2–4 options, each starting with a letter and one
   line of what it means: `A - tabs in the left column: Team and Specifications start level
   with it`. The recommendation names the letter and the reason.
4. **Not a question → a note.** Something the owner only needs to know (the Figma file could not
   be opened, so the layout follows D4/D6–D9) goes under `notes`, not into a question. Ask
   only if you would do something different depending on the answer.
5. **Write it down before you ask.** Every question goes into `job.json.questions` (below)
   **before** the `ask` / end of turn. The board shows them from there even when the
   orchestrator has not relayed them yet, and a resumed worker finds them there.
6. **Ask everything at once.** All open questions for this ticket in one go, so the owner can
   answer them together; then end the turn. Do not drip one question per turn.
7. **Never `AskUserQuestion` as a worker.** The owner is not watching your chat. Orca workers use
   `orca orchestration ask`; subagent workers (no Orca) write the questions and end the turn
   with stage `awaiting_owner`.
8. **Record the answers.** When answers arrive, fill `answer` and `answeredAt` on each entry. If
   some are still open, keep waiting; do not guess the missing ones. If an answer opens a new
   fork, add a new entry (next id) and ask it.
9. **Plain ASCII in options.** Use ` - ` rather than an em dash in `options` and
   `recommendation`; some shells write JSON in the wrong encoding and the dash turns into `â€”`.

## `job.json.questions`

```json
"questions": [
  { "id": "PP-017-q1", "kind": "decision",
    "q": "PP-017: where does the tab bar sit on the project page?",
    "options": ["A - top of the left column; Team and Specifications start level with it",
                "B - full width above both columns"],
    "recommendation": "A - keeps the right column's cards aligned with the content",
    "askedAt": "2026-11-11T23:25:00+08:00", "messageId": null,
    "answer": null, "answeredAt": null },
  { "id": "PP-017-q2", "kind": "decision",
    "q": "PP-017: should switching tabs add browser history entries?",
    "options": ["A - no (replaceState): Back leaves the page",
                "B - yes (pushState): Back steps through the tabs you clicked"],
    "recommendation": "A - tabs are a view, not a navigation",
    "askedAt": "2026-11-11T23:25:00+08:00", "messageId": null,
    "answer": null, "answeredAt": null }
]
```

| Field | Rule |
|---|---|
| `id` | `<KEY>-q<n>`, numbered from 1 for the ticket and never reused |
| `kind` | `spec-approval` (accept the record), `decision` (a design fork), `scope` (a path outside the owned ones), `needs-info` (a missing fact), `action` (the owner must do something) |
| `q` | One sentence, starts with the ticket key, ends with `?` |
| `options` | 2–4, each `X - meaning`; `spec-approval` uses `A - accept` and `B - changes needed (say what)` |
| `recommendation` | The letter, then the reason |
| `messageId` | The Orca message id of the `ask`, when there is one |
| `notes` *(optional)* | Things the owner should know that are not questions |

## The `ask` message (Orca workers)

One `ask` per batch, one line per question id, so the orchestrator can relay each as its own
entry:

```text
orca orchestration ask --question "[PP-017] OWNER (2 questions, see job.json.questions):
PP-017-q1 Where does the tab bar sit? A - top of the left column (recommended) / B - full width
PP-017-q2 Tab switches add history entries? A - no, replaceState (recommended) / B - yes, pushState"
```

Then end the turn with a short report that lists the question ids. A spec approval with open
points looks the same: `PP-016-q1` (accept the record?) plus `PP-016-q2`, `PP-016-q3` for the
open points that really are decisions, and everything else under `notes`.

## What the orchestrator does with them (deliver cycle step 6)

- Each open `job.json.questions` entry becomes **one** `ownerQuestions` entry with
  `jobQuestion: "<KEY>-q<n>"`, its own options and recommendation. Never merge entries, never
  summarize several into one.
- Every cycle it sweeps all job folders for open entries it has not relayed (the `ask` message
  is the wake-up; `job.json` is the source of truth).
- It relays every open question, not a capped batch. A worker gets its answers when all of its
  open questions are answered, or when the owner says "go with your recommendations".
