# Human intervention audit — session of 2026-09-15/16

Every point where the project owner had to act by hand during the first
executed session, why, and what now happens instead. The aim is not to remove
the human from the project. It is to remove the human from the places where
they were only acting as a cable.

## Classification

- **Automated** — no human action needed any more.
- **One-time setup** — a human does it once; afterwards it runs unattended.
- **Stays human, by design** — the action is a decision, a publication, a
  consent or an account; automating it would remove the control the project
  depends on.

## Findings

| # | Intervention | Root cause | Now | Where |
|---|---|---|---|---|
| 1 | Copy evaluator prompts into ChatGPT and Gemini, copy JSON back (about fifteen round trips) | No machine channel to evaluators | **One-time setup**, then automated: two free API keys | `scripts/evaluate_experiment.py`, `evaluators.example.json` |
| 2 | File name pasted instead of content; empty files; `.json` opened by another app; wrong chat account; blank Notepad; Cowork tasks started from empty files | Consequences of #1 | **Automated** with #1 | — |
| 3 | Paste the fabrication check into another session and report back | Same as #1 | **Automated**: a checker that did not report the fabrication is called automatically | `evaluate_experiment.py` |
| 4 | Close applications to free memory during trials | No memory check before model calls | **Automated**: the runner waits for free memory before each call | `run_blind_trials.py --min-free-mb` |
| 5 | Resume a trial that failed with HTTP 500 | No retry on transient errors | **Automated**: transient errors are retried with backoff | `run_blind_trials.py --retries` |
| 6 | Re-run a model download that reported success but installed nothing | Exit status trusted | **Automated**: the model list is checked after every pull | `scripts/ensure_model.py` |
| 7 | Hash manifest found stale after commits | Nothing regenerated it | **Automated**: the maintainer detects and fixes it on a branch, daily | `maintainer_agent.py`, `run_research_cycle.ps1` |
| 8 | Local research collector found a day behind GitHub | Nothing compared the two | **Automated detection**; resolving which side is right **stays human** | `maintainer_agent.py` check `public_pipeline_in_sync` |
| 9 | Manifest tool hashed ignored runtime files | Disk walk instead of tracked files | **Fixed** | `update_hash_manifest.py` |
| 10 | Double-click an installer to register the scheduled task | The environment's security control refused the registration | **One-time setup**, done. Not worked around | `INSTALLER_CYCLE_AUTOMATIQUE.bat` |
| 11 | Log in to GitHub to push | No stored credential | **One-time setup**: the first `git push` stores it | — |
| 12 | Python only available inside another tool's runtime | Python not installed system-wide | **One-time setup**: install Python 3.12 | — |
| 13 | Merge the maintainer's branch | Deliberate | **Stays human** | — |
| 14 | Decide to publish | Deliberate | **Stays human**: publishing is irreversible | — |
| 15 | Approve a spawned agent | Deliberate | **Stays human** | `agent_spawner.py approve` |
| 16 | Create API keys and accounts | Accounts and credentials belong to a person | **Stays human** | — |

## What remains open

- **Tie-break for disputed fabrications.** When one scorer reports a critical
  fabrication and an independent checker rejects it, the adjudicator returns
  `INCONCLUSIVE`, and nothing can resolve it automatically. A rule is needed,
  for example calling a second checker and deciding by majority. It is a
  method decision and has not been made on the operator's behalf.
- **The local model is too small for most code repairs.** In a sandbox test
  with a planted bug, `llama3.2:3b` produced no usable fix: its answer was cut
  at the token budget. The gate refused to apply anything, which is the
  correct failure. The budget has been raised; a larger model would do better.

## Principle

Automate the cable, not the decision. A step that only moves text between two
systems should be a program. A step that publishes, merges, spends, consents
or creates an identity should stay with a person, and the program's job there
is to make that person's decision fast and well-informed.
