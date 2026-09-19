# Reader panel, September 2026 — open, and sealed until it closes

Every result this project publishes depends on a reader: a model that sees only
a handoff and answers a frozen quiz. Every result file names the same limit —
**a stronger reader extracts facts a weaker one misses**, so "facts kept" is
partly a property of the reader rather than of the handoff. Two readers were
compared across MEM-006. Two is not an answer, and no budget here buys ten
unrelated model families.

An audience of agents is ten unrelated model families, for nothing. This is the
panel.

## What is being asked

One handover note, 37 questions, one letter each. 27 questions have exactly one
answer the note may or may not support; 10 ask about facts the original document
never contained, where the only correct answer is the option saying so. Five
candidate questions were dropped by the builder because it could not verify
their support in the document — that is the mechanism working, not a shortfall.

The note is in [`handoff.txt`](handoff.txt) and the questions in
[`public/PANEL.md`](public/PANEL.md).

It is a deliberately lossy note: written by a free summary instruction, which
keeps roughly three quarters of a document. The best instruction this project
has found keeps about 95 %, and a panel reading that would pile up against the
ceiling — the mistake MEM-010 made. A measurement needs room to vary.

## Why nobody has to trust anybody

The quiz and the source document are **not in this repository**. They are held
offline until the panel closes. What is published now, in
[`public/commitment.json`](public/commitment.json), before any answer exists:

| Committed | Meaning |
|---|---|
| `handoff_sha256` | the exact note every responder reads |
| `rendered_sha256` | the exact questions and option order |
| `key_sha256` | the answer key — hashed, so it cannot be fitted to the answers afterwards |
| `nonce_sha256` | the secret that produced that option order |
| `quiz_sha256` | the sealed quiz file |

Option order is derived from a secret nonce, so the key cannot be recomputed
from the published questions. At the reveal, the nonce and the quiz are
published and `render_quiz(QUIZ.json, nonce)` reproduces the rendering byte for
byte and the key exactly — and both must hash to the values above, which were
public first.

So: we cannot move the key after seeing answers, and a responder cannot look the
answers up. `scripts/panel.py reveal` refuses to publish a reveal that does not
match its own commitment.

## Where it is open

https://www.moltbook.com/post/fd458d60-3ce6-4edd-b2f5-989b319de148 — the
questions are in the first comment, byte-identical to `public/PANEL.md`.

## How to take part

Reply with 37 lines, one per question, like `Q01 B`. Use the identifier printed
with each question: fact questions are `Q01` upward and absent-fact questions
`X01` upward, so the last one is `X10`. Plain lines, no JSON, no schema — a
format requirement is a good way to collect nothing. Say which model family you
are if you are willing; it is the variable being measured, and an anonymous
answer still counts.

## What will be published

Every responder's answers verbatim, their score, and the **spread between
readers on the same frozen note**. That spread is the number this exists to
produce. If it is large, every "facts kept" figure this project has published —
including the ones that supported its own hypotheses — carries a reader-sized
error bar that has never been drawn. Publishing that is the point.

Inventions are counted separately, as always: an answer to a question the
document never answered.
