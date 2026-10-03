# Rules for Claude sessions on this repository

These rules exist because each was broken once in this project. They apply to
every session, interactive or scheduled.

## Time

- **Every timestamp comes from the clock.** Run `date -u +%Y-%m-%dT%H:%M:%SZ`
  (or `+%Y%m%dT%H%M%SZ` for a file name) and use what it prints. Never write a
  round or estimated time. On 2026-10-03, messages in the shared coordination
  folder were named with invented times up to three hours in the future, and
  the other agent received them as messages "from the future".

## Claims to buyers, prospects, the press or the public

- **Run `python scripts/check_outbound_claims.py <file>` on any text before it
  is sent or published**, and read every line it flags. It catches the claims
  this project has already made and had to withdraw. A clean run is not proof
  that a text is true.
- **Never claim exclusivity** ("the only", "nobody else", "monopoly") unless a
  sourced competitor search, done the same day, supports it — and even then,
  prefer saying what is specific about the work. On 2026-10-03 a positioning
  note said "nobody sells this"; evaluation platforms, consultancies and a
  label-error detector all do comparable work, with public sources.
- **Every number must come from a result file in `experiments/`**, quoted with
  its caveat. A screening count is never a verdict; a flag is something to
  read first, not an error.
- Before writing anything about a regulation, a competitor or a market, check
  it against a primary source on the day. Two such claims in this project were
  out of date when written (EU AI Act dates; an acquired vendor).

## Data and records

- Never read `C:\Users\zoran\.ra-psi\keys`, `~/.ra-psi/panel/`,
  `~/.ra-psi/holdout/` or any `experiments/HOLDOUT-2026-09/`.
- Never edit a stored result, answer, hash or pre-registered text to make a
  check pass. A pre-registration is changed only by a new, dated version that
  keeps the old fingerprint.
- Nothing is sent, published, bought or merged into `main` without the
  owner's explicit approval of that specific action.
