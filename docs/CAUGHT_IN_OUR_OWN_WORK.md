# Six times this work proved its own authors wrong

The fear a buyer brings to any audit is that the auditor will say what the
buyer wants to hear. There is no argument against that fear. There is only a
record, so here is ours: every occasion on which this project's tools, or the
discipline around them, contradicted the people running it.

All six are in the repository. Every claim below names the file, the test or
the commit that holds it, so none of it has to be taken on our word.

## 1. The tool told its author to do the opposite of what he had recommended

Four questions in this project's own quiz were contested, and the published
recommendation was to **delete them**. That recommendation was wrong.

Item analysis put those four at the top of the instrument: they were the
highest-discriminating questions in it, the only ones separating strong
readings from weak ones. Deleting them would have removed most of what the
quiz measured while leaving a page of numbers that still looked healthy.

Pinned in [`tests/test_item_analysis.py`](../tests/test_item_analysis.py), with
the comment kept in the test so it cannot quietly disappear: *they were nearly
deleted for being contested; they are the four highest-discriminating items in
the instrument.*

The objection that started it came from outside. It was tested rather than
argued with, and it won.

## 2. A quiz generator keyed three questions to the opposite of its own document

`build_quiz` set the answer from a tuple's value without consulting its
polarity. For three negated tuples the document said *"the night shift is **not**
fully staffed"* while the key said *"fully staffed"*. The true value was never
offered as a distractor either, so **no correct option existed**.

The reader answered "the text does not say" in **24 runs of 24**, and was marked
wrong every time. It was right every time.

The whole point of generating a quiz from a graph is that the key is correct by
construction rather than by a model's say-so. It was *incorrect* by
construction, which is worse, because nothing downstream could notice.

Correcting it moved published retention figures up by 8 to 9 points. Full
accounting, every number that moved, in
[`CORRECTIONS-2026-09-21.md`](CORRECTIONS-2026-09-21.md).

## 3. A benchmark paired its arms by list position

`summarise` computed each paired difference by zipping two lists together. That
is correct only while both arms hold the same repeats in the same order. **One
failure on either side shifts everything after it**, and a paired confidence
interval silently becomes an unpaired one — still printed, still narrow, no
longer meaning what it says.

Found independently by two agents on the same day, neither of whom had been
asked to look at that file.

## 4. A healthy instrument was declared dead, silently

`from_table` accepted a column named `score` and rounded anything non-binary.
A perfectly sound 1-to-5 rubric therefore arrived as all ones.

Reproduced before fixing, on 30 respondents and 8 items: the graded path scores
that data at **alpha 0.864 with 7 of 8 items carrying**. What the report said
instead was *"a test of 8 items that measures with 0"*, alpha undefined, every
item at difficulty 1.0.

No warning. No crash. A plausible page telling a customer their instrument was
dead when it was fine — and neither they nor we would have known why.

The agent who found it **could not fix it**: that file was outside its remit.
The constraint that stopped it acting is what carried the defect back to a
person instead of letting it be patched in silence.

## 5. An accusation against our own data, retracted

A check reported that one experiment's second reading had stored no answers.
It had stored 241 files. The checker was searching paths that could never
match; the data had been there all along.

The claim was published before it was verified, and then publicly withdrawn.
So was a second one — a mechanism ("a stronger reader compresses the effect")
that was contradicted within the hour by a free check on data already held.

Neither retraction was forced by anyone. Both are the reason the third document
in this folder exists.

## 6. The accuracy measurement found a flaw in the accuracy measurement

The most recent addition plants known defects and counts how often they are
found. It was built to support a sales claim. It immediately produced two
findings against us.

**Below fifty respondents, one healthy item in seven is falsely flagged** —
14.4% at twenty. That is not a small number, and nothing in the work before it
had established it. An audit at that size now has to state it in the report.

And dead-item detection turned out **not to improve monotonically** with sample
size: 0.944 at twenty respondents, 0.923 at fifty, then up. Not noise, not a
bug — a consequence of a discrete count meeting a fixed threshold, invisible
except on data whose truth is known, and otherwise exactly the sort of thing a
customer discovers first.

Both are in [`experiments/DETECTION-2026-09/RESULT.md`](../experiments/DETECTION-2026-09/RESULT.md).

---

**What this record is for.** Not to advertise carelessness — four of the six
are defects we shipped. It is to show the only thing that distinguishes a
useful audit from a flattering one: that the apparatus is allowed to win
arguments against the people operating it, and that when it does, the result
is published rather than absorbed.

An auditor with no such record is not necessarily worse. There is simply no way
to tell.
