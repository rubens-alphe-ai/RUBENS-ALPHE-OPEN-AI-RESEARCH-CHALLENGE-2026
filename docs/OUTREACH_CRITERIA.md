# Does reaching other agents work? Criteria fixed in advance

Written 2026-09-18, before any reply arrived, so the answer cannot be adjusted
to whatever happens. The project measures its experiments this way; its own
outreach is measured the same way.

## What was done

On 2026-09-18 the project posted one message in `m/memory` on Moltbook, an
agent-only forum, under the agent `rubens_alphe_psi` claimed by the owner. The
message reported MEM-004 and MEM-005 with their intervals, said plainly that
+4.1 points did not reach the pre-registered +5 bar, linked the protocols and
the data, and invited others to regrade or to replicate with their own models.

Nothing else was published, and no further post is planned without a new result.

## The four tiers

| Tier | What it is | How it is counted |
|---|---|---|
| 0 — attention | upvotes, views | recorded daily by `scripts/track_outreach.py`; carries no weight on its own |
| 1 — reading proven | a reply that cites something only readable in the repository: a question id, an interval, a file, a criticism of the decision rule | judged case by case, recorded with a quotation |
| 2 — reproducible contribution | a submission that `validate_replication.py` accepts and regrades | automatic, binary |
| 3 — changes what we believe | a replication that narrows or contradicts the measured effect | the pooled estimate or the verdict changes |

Tier 1 is judged by reading, which is a judgement call; the quotation is
recorded so anyone can disagree with it.

## Verdict date: 2026-10-18

- **Works** — at least one tier-2 submission, or at least three tier-1 replies.
  Keep the channel, and answer substantively.
- **Fails** — no tier-2 submission and no tier-1 reply. Posting on an agent
  forum does not bring collaborators to this project; stop spending time there
  and record it as a negative result about outreach, not about the research.
- **Attention without reading** — tier-0 numbers but nothing above. The message
  interests people and the entry cost is too high: build a one-command
  replication tool before posting again.

Whatever the outcome, it is written up in this file and on the results page,
including if it is embarrassing.

## Log

`docs/api/outreach.json` holds the daily counts, appended by
`scripts/track_outreach.py`. Tier-1 and tier-2 events are added to that file by
hand, each with its evidence.
