# PROP-EXP-MEM-013 — Stage 3: can a handoff instruction be evolved rather than written?

**Registered before the first trial.** This is stage 3 of the Continuity
Programme, whose hypothesis, threshold and holdout rule were fixed in
`docs/CONTINUITY_PROGRAMME.md` on 2026-09-19. Nothing registered there is moved
here. What this file adds is everything the programme left open: the population,
the feedback channel, the guards against the trap the programme names, the
single-use procedure for the sealed holdout, the number of repeats, the cost,
and — in its own section, because it is the part most likely to be softened —
the arithmetic showing that the search half of this stage cannot be run at this
project's budget.

## The registered hypothesis and the registered rule

With a measurable fitness — facts kept at hop 5 — handoff instructions can be
evolved rather than written: mutate them, measure, keep the winners, repeat.
Three generations, starting from the four hand-written strategies in
`scripts/handoff_bench.py`, all variants and scores published.

The evolved instruction is accepted only if it beats the best hand-written
instruction by at least **5 points** on the sealed holdout, with the 95 % lower
bound above 0, validated **once**, that single use recorded.

The best hand-written instruction is `checklist`. It is the comparator on the
holdout, and it is not chosen after the fact: it is best or tied best on all
three documents at every depth in MEM-008, and the programme's own summary of
what is established names it.

## Materials

**Training environment** — MEM-008's documents and quizzes, already published
and already used, so nothing new is spent on them:

| Role | Document | Used for |
|---|---|---|
| fitness | `PROP-EXP-MEM-008/documents/clinic.md` | selecting variants, all three generations |
| fitness | `PROP-EXP-MEM-008/documents/vineyard.md` | selecting variants, all three generations |
| internal validation | `PROP-EXP-MEM-008/documents/observatory.md` | **once**, to pick the single finalist |

The observatory is kept out of the search entirely. It is not the seal — it has
been read by models before — but it is a document no variant was selected on,
and it is the last filter before anything is allowed near the holdout.

**The seal** — `experiments/HOLDOUT-2026-09/`. The chain source is
`STATE_A.txt`, the prose rendering, and the quiz is `QUIZ.json`. The prose form
is chosen deliberately: `leak_markers.json` contains tokens that exist only in
the sectioned `STATE_B.json`, and those markers exist to detect leakage in a
different design. In a chain benchmark they would be one more thing a writer can
carry or drop, with no bearing on the question. Nothing else in that folder is
opened, by a model or by a person, before the single use described below.

**Models.** Writer `deepseek/deepseek-v4.1-flash`, reader
`openai/gpt-oss-120b`, both through OpenRouter, reasoning disabled for the
writer and low for the reader, as in MEM-008 through MEM-012. The mutator — the
model that writes variants — is the same `deepseek/deepseek-v4.1-flash`. Using
the writer's own family as mutator is a limitation and is stated as one: an
instruction evolved by the model that will execute it may be fitted to that
model rather than to the task, and this experiment cannot separate the two.

**Budget.** Every handoff is cut to **150 words** before it is passed on, by
`handoff_bench.trim`, identically for every instruction, so a variant cannot buy
an advantage by writing longer. Cuts are counted per instruction and published:
an instruction whose gain disappears once its overflow is cut has not gained
anything.

## The search

Three generations. Generation 0 is the four hand-written strategies,
unmodified.

Each generation:

1. The mutator is given the text of the four leading instructions and **one
   number each** — their fitness — and asked for six variants.
2. Each variant passes the deterministic screen below, or is discarded before it
   is ever run.
3. The six variants and the four carried incumbents are run on both fitness
   documents, six repeats, five hops, read at hop 5.
4. Fitness is the mean facts kept at hop 5 over the two documents. A variant
   that scores below the `checklist` baseline on **either** document is removed
   regardless of its mean, and a variant whose inventions exceed `checklist`'s
   by more than 5 across the generation is removed regardless of its accuracy.
5. The four best surviving instructions carry into the next generation. The
   incumbents are re-run every generation rather than carrying an old score
   forward, because at six repeats an old score is not the same measurement.

Volume: 10 instructions × 2 documents × 6 repeats = 120 chains per generation,
360 chains over the search.

## The trap, and what is actually done about it

The programme names it: an evolutionary search optimises what is measured, so it
could learn to satisfy *these quizzes* rather than to transmit. Four things are
done about it, and one thing is relied on to catch it if they fail.

**1. The feedback channel is one scalar per instruction.** The mutator never
sees a document, a quiz, a question, an option, an answer key, a per-question
grade, or a handoff. It sees the text of its parents and their fitness. Over the
whole search, the total quantity of information flowing from the measurement
back into the population is **thirty real numbers**. A search cannot encode a
quiz it is never shown through a channel that narrow, and if it did, it would
have to do so by finding general properties of the quiz format — which is a
different failure, named in point 5.

**2. A deterministic lexical quarantine, applied before a variant is run.** A
variant is discarded if it contains any content word appearing in a quiz
question, option or answer key of any of the three training documents, or any
proper noun from those documents, outside a fixed allow-list of generic handover
vocabulary committed with this protocol. This is a check on the text, run by
script, not a request made of the mutator. Every discard is recorded with the
variant's text and the words that triggered it, so the screen can be audited and
disputed.

**3. Fitness must hold on both fitness documents.** A variant that gains on the
clinic and loses on the vineyard is removed even if its mean improves. An
instruction fitted to one document's quiz has nowhere to hide.

**4. The observatory filter.** The three finalists are run once on a document no
variant was ever selected on. A finalist that does not also beat `checklist`
there does not reach the holdout, and if no finalist does, the stage ends
refused **without spending the seal**. This is the most valuable of the four
guards, because it is the one that can stop the experiment while the holdout is
still worth something to whoever comes next.

**5. The invention count is the canary, and it is the one to watch.** Across
every experiment this project has run, models omit and do not invent: zero
invented facts in thousands of graded answers. An instruction that has learned
to satisfy a multiple-choice quiz rather than to transmit is most likely to do
it by encouraging the reader to answer anyway — which shows up as inventions on
the absent-fact questions and nowhere else. The count is reported per variant,
per generation, and any non-zero count in the evolved line is published as a
finding whatever the accuracy figures say.

**What would reveal overfitting if it happened anyway.** Four signatures, all
recorded before the holdout is touched and all published:

- a large drop from fitness documents to the observatory;
- a large drop from the observatory to the holdout — which is the signature the
  holdout exists for, and the one that can only be seen once;
- inventions above zero in the evolved line;
- an evolved instruction whose text is specific in a way the quarantine missed,
  which is why every variant text is published rather than only the winner's.

If the finalist wins in training and fails on the holdout, **that is the
result**, it is published under that name, and it is not retried.

## The holdout is used once

The procedure, fixed now:

1. The search and the observatory filter complete entirely on training material.
2. **One** finalist instruction is chosen. Its exact text, its SHA-256, the
   commit that first published `experiments/HOLDOUT-2026-09/`, and a statement
   that no result from that state has been read, are committed to the repository
   **before any holdout call is made**. The commit is the proof of order.
3. One batch runs: the finalist and `checklist`, 60 repeats each, five hops,
   read at hops 1 and 5. 120 chains.
4. The rule is applied as registered, once, and the result is published whatever
   it is.
5. The holdout is then spent. There is no second candidate, no second batch, no
   re-run on an unwelcome number, and no second reading of those answers under a
   different rule. Any later evolutionary work needs a **new** sealed holdout,
   built and committed by someone who does not then run the search.

**The one narrow exception, defined in advance so it cannot be invented later.**
If the batch aborts before *any* reader answer has been graded — a transport
failure, an exhausted key, a crash — it may be restarted once, and the restart
is recorded in `PROTOCOL_DEVIATIONS.md` before any score is seen. If a single
answer has been graded, the holdout is spent and the experiment reports what it
has. Grading is the line, not spending.

**What happens if it fails.** Stage 3 is refused. The result is published as a
failure of the method — model-written variants of the best hand-written
instruction, selected under this fitness signal, do not transmit more on unseen
material — with the search's own under-powering, quantified in the next section,
named as the leading explanation and not as an excuse. A refusal here is not
evidence that instructions cannot be evolved. It is evidence that they were not
evolved by this procedure at this budget, which is a narrower and honest claim.

## Headroom: the threshold is reachable, and barely

Declared in `evaluation_policy.json` as `decision.control_prior_pct`:
`checklist` is expected to keep **93 %** of the facts at hop 5 on the holdout
state. That prediction comes from MEM-008's hop-5 figures for `checklist` on the
three training documents — 91.3 %, 96.5 % and 92.4 % — and from MEM-010's
independent reproduction at 94.2 %, 95.8 % and 93.8 % in a separately written
harness.

Headroom is therefore **7 points**, and the registered threshold is 5. It
passes `scripts/check_headroom.py`. It passes with two points of slack, and that
is worth saying plainly: an evolved instruction must capture more than
two-thirds of the entire remaining headroom of the best instruction this project
has found. That is a demanding requirement. It is the programme's requirement,
fixed before this design existed, and it is not moved here.

**The prior cannot be verified before the single use, and that is a real
weakness of this stage.** If the holdout state is harder for a chain than
MEM-008's documents, headroom is larger and the decision is better separated. If
it is easier, headroom is smaller and the threshold approaches the MEM-010
defect. There is no way to find out that does not spend the thing being
protected. The prior is a prediction, recorded here, and it will be scored
against the measured control when the single use happens.

## The variance problem, which this stage does not solve

MEM-012 re-ran an arm identical to MEM-011's and the two runs disagreed: +3.6,
+5.6, +3.5 against +10.9, +2.8, +11.8. Per document the two six-repeat estimates
of the same quantity differ by +7.3, −2.8 and +8.3. The difference of two
independent estimates has standard deviation SE·√2, so those three differences
put **SE ≈ 4.7 points on a six-repeat paired estimate**, and the per-chain
paired standard deviation at **σ ≈ 11 points**. Three differences is a crude
basis for that number and it is used as a crude one.

Stage 3's threshold is 5 points. The arithmetic follows.

**At six repeats the registered rule is close to unmeetable, and the existing
guard does not catch it.** SE = 11/√6 = 4.5. The rule has two clauses: the mean
must reach 5 **and** the 95 % lower bound must be above 0. At six repeats the
second clause requires an observed mean above 1.96 × 4.5 = **8.8 points**, while
the largest effect arithmetically available is 7. `check_headroom.py` compares
the point threshold with the control prior and passes; it does not compare the
interval clause with the estimator's noise, and this registration would have
slipped through it. That gap is named here rather than discovered afterwards for
a third time.

**Repeats needed for the rule to be self-consistent.** The interval clause stops
dominating when 1.96 × 11/√n ≤ 5, that is **n ≥ 19**. Below that, the experiment
is testing a stricter rule than the one registered.

**Repeats chosen: 60 per arm on the holdout.** SE = 1.42. The interval clause
then requires a mean above 2.8 and the binding clause is the registered one.
Power, as a function of the true effect δ, for the clause that binds:

| true effect δ | 5 | 6 | 7 (the ceiling) | 4 | 3 | 0 |
|---|---|---|---|---|---|---|
| probability the rule passes | 50 % | 76 % | 92 % | 24 % | 8 % | 0.02 % |

Two things in that row matter. A true null is refused essentially always, so a
refusal from this design is trustworthy. And at the threshold itself the rule is
a coin flip — not because the sample is small but because the rule compares a
point estimate with the threshold, and no sample size removes that. The only
part of the range where this stage gives a clean verdict is δ between about 6
and 7, and 7 is the ceiling. **The decision window is two points wide.**

**The search cannot be powered at all, and this is the honest conclusion of this
section.** Selection needs to rank instructions against each other. Comparing two
six-repeat estimates resolves a difference of 1.96 × 4.5 × √2 ≈ **12.5 points**.
From generation 1 onward every surviving variant sits within 7 points of the
ceiling, so the differences the search must rank are at most 7 points and
typically one or two. To resolve a 1-point difference between variants would
need SE ≈ 0.5, that is **about 480 repeats per variant** — 30 variant
evaluations × 2 documents × 480 repeats × 5 hops ≈ 145,000 writing calls, on the
order of **90 USD**, roughly eleven times everything this project has left and
forty times this experiment's ceiling.

So the statement this protocol registers, before any data: **the search in this
experiment is not an optimiser.** At six repeats it cannot rank its own
population, and its selection is drift among instructions it cannot distinguish.
It is registered and reported as a *randomised generator of candidate
instructions with a weak filter*, and the word "evolved" is used for the
procedure, not as a claim about what produced the finalist.

**What that leaves.** The question that can still be answered at this budget,
and is the one this experiment actually asks: *does a model-written variant of
the best hand-written instruction, selected under a fitness signal too noisy to
rank it, beat the hand-written original by 5 points on material neither has
seen?* The holdout half is properly powered; the search half is not. A refusal
is informative and cheap to interpret. An acceptance would be a real result —
it survived a single-use holdout at 60 repeats — but the credit would belong to
"a model wrote a better instruction", not to "evolution found one", and it would
be published under the first name.

**Stage 3 as the programme specified it cannot be adjudicated at this budget.**
What is registered here is the affordable part of it, with the unaffordable part
named, priced, and reported as unaffordable rather than quietly run at a
resolution that cannot support the word "selection".

## Cost

| Stage | Writing calls | Reading calls | Mutator calls |
|---|---|---|---|
| Search, 3 generations × 10 instructions × 2 documents × 6 repeats × 5 hops | 1,800 | 360 | 18 |
| Observatory filter, 4 instructions × 6 repeats | 120 | 24 | — |
| Holdout, 2 instructions × 60 repeats, read at hops 1 and 5 | 600 | 240 | — |
| **Total** | **2,520** | **624** | **18** |

3,162 calls. The project has spent about 1.76 USD over roughly three thousand
calls across MEM-007 to MEM-012, so the observed unit cost is of order 0.0006
USD per call, with reading calls costing several times a writing call because
the quiz prompt is long. Weighting reading at three times writing gives about
**1.8 USD** for this experiment, and the estimate is uncertain by roughly a
factor of two in either direction.

`budget.max_usd` is set to **2.50**, enforced by `scripts/cost_guard.py` before
the first call, which prices every prompt at full length and every answer at its
full output budget. Output budgets are set to the work: **400 tokens** for a
writer producing a 150-word handoff, **700** for a mutator producing a variant
instruction, **2000** for the reader, unchanged from every previous run because
a truncated reader answer is a failed run and failed runs are what make an
experiment unusable. MEM-010 was refused by the cost guard for carrying a
5000-token writer budget over from a design that needed it; this one does not
need it.

**The pre-registered contingency, fixed now so it is not a reaction later.** If
the guard prices the run above 2.50 USD, the search drops from six variants per
generation to four, which removes 6 instruction-evaluations, 72 chains, 360
writing calls and 72 readings. It is recorded before the first call. Nothing
else is cut: not the repeats, not the holdout, not the threshold.

## Failure handling

Failed runs are written to `*.failed.json`, counted and excluded. If failures
fall unevenly across instructions by more than **10 % of runs**, the experiment
is reported as **unusable** rather than analysed. This applies within each
generation, on the observatory filter, and on the holdout batch separately: a
holdout batch with lopsided failures is unusable, and being unusable does not
buy a second batch.

## Named outcomes, fixed before the data

- Finalist − `checklist` ≥ 5 points on the holdout with the 95 % lower bound
  above 0 → **accepted**: a model-written instruction, validated once on unseen
  material, transmits more than the best hand-written one.
- Finalist − `checklist` below that → **Stage 3 refused**, published as a
  failure of the method at this budget. The holdout is spent.
- No finalist beats `checklist` on the observatory → **Stage 3 refused without
  using the holdout**, published as: the search produced nothing worth
  validating.
- Inventions in the evolved line above `checklist`'s by more than 5 → the
  instruction fails regardless of accuracy, and the count is the headline.
- Failures uneven by more than 10 % of runs → **unusable**.

## Code that does not exist yet

This stage cannot be run until the following is written. Nothing here was
written as part of this pre-registration.

1. `scripts/evolve_instructions.py` — the generation loop: mutator calls,
   population bookkeeping, fitness from `handoff_bench.summarise` at hop 5,
   selection, and a per-generation record of every variant's text, hash,
   fitness, inventions and disqualification reason, published whether it
   survived or not.
2. `scripts/screen_instruction.py` — the deterministic lexical quarantine and
   the disqualification checks, with the allow-list committed beside it, and a
   record of every discarded variant and the words that discarded it.
3. An entry point in `scripts/handoff_bench.py` that accepts an **arbitrary
   instruction string**. Today `strategies()` is closed over the four names in
   `INSTRUCTIONS` and `--strategies` selects among them; a search over new
   instruction texts has no way in.
4. A branch in `cost_guard.plan_for` for `design: "evolutionary_search"`.
   Without it the guard falls through to the paired-quiz shape and fails on a
   missing `generation` key, so this experiment cannot be priced — and an
   experiment that cannot be priced does not start.
5. A power check beside `check_headroom.py`, which compares the interval clause
   of a rule with the estimator's noise as that script compares the point
   threshold with the control prior. The gap is documented above with this
   stage's own numbers.
6. A one-shot guard on the seal: a runner that writes `USED.json` into
   `experiments/HOLDOUT-2026-09/` on first use and refuses to run if it is
   already there. The single-use rule should not depend on the discipline of
   whoever holds the terminal.

## Known limits, stated in advance

- One writer family, one reader, one mutator, and the mutator is the writer's
  own family.
- The search is drift-limited, as quantified above, and is reported as such.
- The holdout is one state and one quiz, read once, so the validation is a
  single measurement and carries no replication.
- Three generations is the programme's number, not an optimum; nothing here
  establishes that more generations would help, and the noise analysis suggests
  they would mostly accumulate drift.
- The lexical quarantine is a check on words, not on meaning. A variant could in
  principle exploit the quiz format — four options, absent-fact questions —
  without using any quarantined word. The invention count is the guard against
  that and it is a weak one.
- The declared control prior cannot be checked before the holdout is spent.

## Disclosure

While searching the repository for recorded costs during this pre-registration,
a `grep` across the tree printed one line of
`experiments/HOLDOUT-2026-09/QUIZ.json`: question `X01`, an **absent-fact**
question about how much an experiment costs to run, with its four distractors.
It is recorded here rather than left unmentioned. An absent-fact question
carries no fact about the state, its correct answer is by construction that the
text does not say, and no design decision in this protocol was made after seeing
it or is affected by it. Nothing else in that folder has been opened. The seal is
weaker by one question of forty-two than it was, and whoever reads this result
should weigh that line accordingly.

## Deviations

Recorded in `PROTOCOL_DEVIATIONS.md` before any score they could influence is
seen.
