# Panel readings that did not complete

These are not readings. They are collection attempts that stopped before enough
trials finished to support any number, and they are kept out of `results/`
because a `decision.json` sitting beside the real ones is read as a reading.

| Reader | Pairs completed of 60 |
|---|---|
| `qwen/qwen3.8-27b` | 1 |
| `nvidia/nemotron-3-super` | 0 |

The individual trials that *did* complete look normal — Qwen parsed all 42
answers and scored 84 % on its one pair. So this is not a model that cannot read
the quiz; it is a run that did not finish, most likely on provider rate limits.

**What this costs the panel.** It is a panel of three completed readers, not
five, and it must be reported as such. Two families are untested here, and
"untested" is not "agreed".
