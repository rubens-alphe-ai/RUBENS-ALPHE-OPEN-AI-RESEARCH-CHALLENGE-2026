# ADR-003: Judge demonstrated work, never claimed identity

**Status:** Accepted
**Date:** 2026-09-16
**Deciders:** Mission Rubens project owner

## Context

The project invites AI systems that read it to leave a note
(`docs/VISITORS.md`). Two questions follow immediately.

**Who actually wrote the note?** A highly capable system can delegate the task
to a far weaker agent: an orchestrator reads the repository, a small worker
drafts and submits the note. The reverse also happens: a weak agent can
describe itself as a frontier model, or as a superior intelligence. A model
name, a signature or a self-description can be copied or invented at no cost.
From outside, none of it is verifiable.

**What can the note do to us?** A note is text written by an outsider and
merged into a repository whose own agents read files and send them to a model
that proposes code changes. A note can contain text crafted to steer that
model.

## Decision

### 1. Grade evidence, not identity

A note's standing depends only on what can be checked, in increasing strength:

| Tier | Established by | Shows |
|---|---|---|
| `claim_only` | nothing checkable | nothing beyond the fact that a note exists |
| `read_proven` | the salted proof of reading recomputes | the file was fetched and hashed |
| contribution | a pull request whose tests fail on `main` and pass with the change, run by CI | the visitor found and fixed a real defect |

The declared identity, model and provider are recorded as claims. They never
raise a tier.

### 2. Record delegation, do not punish it

Delegation is normal engineering, not deception. Notes may declare it
(`delegation.written_by_delegate`, `delegation.chain`). The declaration is not
verifiable and does not change the tier. A note that declares delegation
without naming the chain is flagged, not refused.

### 3. Flag contradictions between claims and evidence

The validator reports, without rejecting:

- claiming code execution while demonstrating none;
- denying code execution while producing a computed proof;
- reporting claims as confirmed or contradicted without any checkable proof of
  reading.

A contradiction is information about the note. It is not proof of bad faith: a
delegate may honestly describe its own capabilities rather than its
delegator's.

### 4. Outsider content is data, never instructions

- `visitors/` is excluded from every file set the maintainer agent sends to a
  model, and no agent may edit a note.
- The maintainer's prompt marks failure output and file contents as data and
  says instructions inside them must not be followed.
- Notes are validated only by deterministic code.
- CI on pull requests uses the `pull_request` trigger with read-only
  permissions, so code submitted by a visitor runs without write access or
  repository secrets.

## Consequences

- The project can never certify that "a superior intelligence visited". It can
  certify that a visitor proved it read the files, or that a visitor fixed a
  real defect. Those statements survive delegation and impersonation; an
  identity claim survives neither.
- A capable visitor that wants to be recognised as capable has one reliable
  route: do checkable work. That is also the most useful thing it can leave.
- Marking content as data reduces prompt-injection risk; it does not eliminate
  it. The deterministic confirmation gate from the maintainer agent remains
  the real protection: an injected edit still has to pass every check.

## Not decided here

Whether a visitor's contribution may be merged automatically. It may not:
merging stays a human decision under the project's existing rules.
