# Acceptance criteria — Provenance Guard

Five criteria that say what "working" means for this service, written in unit 7
**before** you built it.

**All five are yours.** None are given.

An acceptance criterion names a number or something plainly observable. *"The
detector is accurate"* is an opinion — and perfect AI detection isn't possible
anyway, so it's an opinion about something nobody can deliver. *"Of 10 pieces I
wrote myself, at most 1 is labelled high-confidence AI"* is a criterion.

Under each, write a sentence or two on **why that target**. *"I allow at most 1
false positive in 10 because on a writing site a wrong accusation costs more
than a missed detection"* is a real answer.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## Pick numbers you can defend

**Cover at least three of these five areas.** They're prompts, not a form.

| Area | A question it could answer |
|---|---|
| False positives | How often may a human's writing get called AI? |
| Score spread | How far apart should clearly-AI and clearly-human text score? |
| Label coverage | Is every one of your three labels actually reachable? |
| The appeal path | Does an appeal always change status and always get recorded? |
| Bad input | What happens when `text` is missing, empty, or enormous? |

Two things worth knowing before you pick numbers:

- **The expensive mistake is one-sided.** Missing some AI text costs the site a
  little. Accusing a real writer costs that person a lot. A criterion that
  treats both errors as equally bad is describing a system nobody would ship.
- **Unit 8 tests across three trials, and the target has to hold across all
  three.** Your first signal runs a model, so identical input can score
  differently twice. A target of "at most 1 in 10" against trials of 2, 1, 2 is
  a **miss**.

---

## 1. Limit false AI accusations on human writing

**Target:** Of ten fixed pieces written without AI generation or rewriting,
submitted to `POST /submit`, at most **one** returns `guess: "ai"` in each
trial. All ten must return HTTP
200 with a valid guess and an error does not count as avoiding a false positive.

**How to measure:** Count the human submissions labeled `ai` out of ten.
`unsure` is not counted as an AI accusation, but also is not evidence that
the system correctly identified the author as human. Select and save the ten
pieces before inspecting their evaluation scores, keep them separate from
calibration inputs, and reuse them in all three trials. The target must hold
in every trial.

**Why this target:** A wrong AI accusation can harm a real writer, so at most
one in ten tightens the original 20% allowance to 10% while allowing an
occasional mistake in this prototype. Ten pieces also provide room for more
varied writing, passing this small sample would not establish a
population-wide false-positive rate or production readiness.

---

## 2. Reach all three labels through real submissions

**Target:** Across fifteen fixed pieces (the ten human pieces from criterion 1
and five pieces with known AI-generation origins) sent to `POST /submit`,
each of `human`, `unsure`, and `ai` appears at least **once** in every trial.

**How to measure:** Collect the distinct `guess` values from fifteen successful
responses. The required set is exactly `{"human", "unsure", "ai"}`. Submit
actual text through the endpoint; passing invented scores directly to the
label-mapping function does not demonstrate this criterion. Select and save
the five AI pieces before inspecting their evaluation scores, record their
generation sources, and keep them separate from calibration inputs. Reuse
the same fifteen texts in all three trials and for criterion 5, do not replace
samples after seeing their scores.

**Why this target — proposed rationale:** Three label branches in code do not
guarantee that the two signals can produce scores reaching all three. One
real submission per label is the minimum demonstration of reachability.
Correctness and score separation are checked separately rather than assuming
that label coverage proves detection quality.

---

## 3. Record every valid appeal as under review

**Target:** For **five out of five** valid appeals against distinct, freshly
created submissions in each trial, `POST /appeal` returns HTTP 200 with the
same `content_id` and `status: "under_review"`, backed by a newly appended
appeal event with that ID, status, and submitted reasoning in the audit log.
The original decision entry must remain unchanged.

**How to measure:** Save the original decision entries, submit one nonblank
explanation for each ID, then compare the responses and
`GET /log` entries. Count an appeal as passing only when the response and
stored transition agree and the original record is preserved. A confirmation
response alone is insufficient.

**Why this target — proposed rationale:** An appeal is the writer's way to
challenge an assessment, so silently losing even one accepted appeal defeats
that path. All five should work because recording a valid appeal is a service
guarantee, not an uncertain authorship prediction. Five distinct IDs check
that the service links each appeal to the right submission.

---

## 4. Reject invalid submissions with defined client errors

**Target:** In every trial, **all eight** cases below sent to `POST /submit`
return the specified HTTP status and a JSON object containing nonempty string
fields `error` and `message`, without a classification `guess`.

Use `Content-Type: application/json`. Include a valid `creator_id` in each
object except the case explicitly testing its absence. case 6 is a whole
JSON array rather than an object.

| Case | Invalid request condition | Required HTTP status |
|---|---|---|
| 1 | `text` field missing | 400 |
| 2 | `text` is `""` | 400 |
| 3 | `text` contains only spaces | 400 |
| 4 | `text` is JSON `null` | 400 |
| 5 | `text` is the number `42` | 400 |
| 6 | Whole request body is `[]` | 400 |
| 7 | `creator_id` is missing; `text` is otherwise valid multi-sentence writing | 400 |
| 8 | `text` contains exactly 20,001 characters | 413 |

**How to measure:** Record the response status and JSON body for each case.
A timeout, HTTP 500, or a success response assigning a label fails the case.
Case 8 uses the chosen maximum of 20,000 characters, including whitespace.

**Why this target — proposed rationale:** These requests cannot be assessed
under the endpoint contract, so they should always receive an explicit client
error rather than a crash or misleading classification. The eight cases cover
missing values, empty content, wrong types, a non-object body, and a size-boundary
violation. The 100% target applies to these named cases, not every possible
malformed request.

---

## 5. Separate known human and AI writing by score

**Target:** In each trial, the mean combined AI-likeness score for the five
fixed AI-generated pieces is at least **0.20 higher** than the mean for the
ten fixed human-written pieces:
`mean_AI(confidence) - mean_human(confidence) >= 0.20`.

**How to measure:** Use `confidence` from the fifteen successful `/submit`
responses, as defined in the README: the combined score where higher means
more AI-like. Calculate the two means and their difference separately for
each trial. Every score must be a finite number within 0–1, missing or invalid
scores fail the criterion. Preserve individual scores as well as the means.

**Why this target:** Avoiding false accusations alone could let a system pass
by returning human or unsure almost everywhere. A minimum mean-score gap of
0.20 requires separation equal to one fifth of the 0–1 scoring range rather
than a tiny numerical difference, while allowing individual scores to overlap.
The exact margin is a chosen engineering target, not an empirically established
detection standard or an accuracy percentage. Both group means could still
fall in the unsure band, so this criterion complements label coverage and
false-positive testing rather than replacing them.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 8 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath, like this:

         ## 2. Uncertain cases land in the unsure band

         The system handles uncertain cases well.

         **Why this target:** ...

         > **Revised in unit 8:** Text I judged borderline scores between
         > 0.4 and 0.6 in at least 4 of 5 cases.
         >
         > **Why revised:** "well" gave me nothing to check. I couldn't
         > reach a verdict from it at all.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "At most 1 of 10 of my own pieces flagged as AI" → "at most 3
            of 10", because 1 of 10 turned out to be hard.

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
