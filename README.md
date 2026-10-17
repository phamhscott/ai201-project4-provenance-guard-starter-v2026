# Provenance Guard

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first.**
>
> Once `python test.py` passes, in one terminal:
>
> ```bash
> python app.py
> ```
>
> and in another:
>
> ```bash
> curl -X POST http://127.0.0.1:5000/ping \
>   -H "Content-Type: application/json" \
>   -d '{"message": "hello"}'
> ```
>
> That's a web service. Something sent it text and it sent something back.
> Everything this unit is filling in the middle.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     Unit 7 asks for the first five sections. Unit 8 adds the five below.

     Everything is pasted as TEXT. A pasted curl response gets full credit;
     a picture of your terminal gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 7 — THE BUILD ═══════════════════════ -->

## What This Does

<!-- The path a submission takes, from arriving to the label a reader sees.
     Six or seven steps — this is the trace you wrote in Milestone 1. -->

Provenance Guard assesses writing authorship (human or AI) using a
language-model signal and a style signal. It returns a human, unsure, or AI
label, saves the decision, and lets the writer challenge it through an appeal.


**The submission path**

1. A writer sends their writing as `text` and their identifier as `creator_id`
   to `POST /submit` in `app.py::submit`.
2. The route checks that the body is a JSON object, both required fields are
   nonblank strings, and the text is at most 20,000 characters. Invalid input
   receives a defined error instead of a classification.
3. `detector.py::model_signal` measures how predictable the text is to the
   local language model. It returns `model_score` between 0 and 1, with higher
   scores meaning more AI-like according to this signal.
4. `stylometry.py::style_signal` measures sentence-length variation and
   vocabulary repetition and converts them into `style_score`, also between
   0 and 1 with higher meaning more AI-like. Punctuation density is computed
   separately for diagnosis and does not contribute to this score.
5. `scoring.py::combine_signals` combines the two scores using a documented
   rule: `0.5 * model_score + 0.5 * style_score`, rounded to four decimal
   places. The route then creates a unique `content_id` to connect the
   response, audit record, and any later appeal.
6. `scoring.py::score_to_label` maps that score to `human`, `unsure`, or `ai`
   and a full sentence for the reader. `audit.py::log_decision` records the
   identifiers, both signals, the combined score, the guess, the label, a
   timestamp, and the initial status `decided` before the route returns them.
7. The route returns `content_id`, `guess`, `confidence`, `label`, both signal
   scores, and `status`. The caller can display the label to the reader.
   If the writer disputes
   it, they send the `content_id` and their explanation to `POST /appeal`.
   `app.py::appeal` finds the original submission and calls
   `audit.py::log_appeal` to append an `under_review` event. The response confirms
   that status and does not automatically reverse the original decision.

### Following a false positive

Consider a writer who wrote a paragraph themselves using
common words and short, similarly sized sentences. The model might find it
predictable, while the style rules might find it unusually uniform. These are
overlapping blind spots where the two signals agreeing would not prove authorship.

For a hypothetical arithmetic example, suppose `model_score = 0.90` and
`style_score = 0.70`. The equal-weight combining rule produces `0.80`.
With the current AI cutoff of `0.65`, the guess would be `ai`, and the exact
reader-facing label would be:
"Our signals suggest this text may be AI-generated. This assessment can be
wrong. You can request a review if you disagree."

The writer can appeal using the returned `content_id` and explain how they
wrote the paragraph, mentioning drafts or notes if available. The
endpoint accepts an explanation as text, it does not upload or verify that
supporting material. The appeal response says `under_review`, and the audit
log retains both the original decision and the later challenge. Recording an
appeal does not by itself provide a reviewer or a final resolution.

This example is a reason to examine a wider `unsure` band before making a
strong AI claim. That could reduce false accusations while letting more AI
writing avoid the AI label.

### Endpoint contracts

Both endpoints accept `Content-Type: application/json` with a JSON object and return JSON.
Required strings must contain something other than whitespace. Validate with
whitespace stripped, but score the submitted text as supplied. Extra request
fields are ignored. `creator_id` is a caller-supplied identifier, not verified
identity.

#### `POST /submit`

Request fields:

| Field | Type | Meaning |
|---|---|---|
| `text` | string, required | The writing to assess. Maximum: 20,000 characters, including whitespace. |
| `creator_id` | string, required | The identifier to associate with this submission and its audit records. |

Successful response: **HTTP 200**.

| Field | Type | Meaning |
|---|---|---|
| `content_id` | string | A new UUID for this submission, pass this value unchanged when appealing. |
| `model_score` | number, 0–1 | The model's AI-likeness signal. |
| `style_score` | number, 0–1 | The style rules' AI-likeness signal. |
| `confidence` | number, 0–1 | The combined AI-likeness score, equal to `combined_score` in the audit log. Higher means more AI-like. This is not a verified probability or certainty in the selected label. |
| `guess` | string enum | Exactly `human`, `unsure`, or `ai`, according to the combined score's label range. |
| `label` | string | The complete reader-facing sentence for that guess, written out in **Label Variants**. |
| `status` | string | Initially `decided`. This records that a decision was made, not that it is correct. |

The combined score must be finite and within 0–1. Label ranges must cover
that whole interval without gaps or overlapping boundary assignments.

Errors use `{"error": "<code>", "message": "<explanation>"}`:

| HTTP status | `error` | When |
|---|---|---|
| 400 | `invalid_request` | Missing or malformed JSON, a non-object body, or a required field that is missing, not a string, or blank. |
| 413 | `text_too_long` | `text` exceeds the 20,000-character limit. Reject before running either signal. |
| 422 | `text_too_short` | Otherwise valid text has fewer than three tokens with the detector's tokenizer, so the supplied detector cannot score it. |
| 503 | `detector_unavailable` | The local model cannot load. Return an error rather than inventing a score. |

The character limit is the agreed input bound, not the model's reading window:
the starter detector reads at most 400 tokens, while the style signal
measures the whole accepted text. An accepted long submission therefore does
not mean the model assessed every word. Rate-limit errors are added in Unit 8.

#### `POST /appeal`

Request fields:

| Field | Type | Meaning |
|---|---|---|
| `content_id` | string, required | The identifier returned by a successful submission. It must match an existing original decision. |
| `reasoning` | string, required | The writer's explanation of why they dispute the assessment. |

Successful response: **HTTP 200**, after the appeal has been logged.

| Field | Type | Meaning |
|---|---|---|
| `content_id` | string | The same identifier supplied in the request. |
| `status` | string | Exactly `under_review`. |
| `message` | string | `Your appeal has been recorded. The submission is under review.` |

Use the original decision to recover `creator_id` for the appeal log, the
caller does not need to send it again. An appeal can dispute any existing
decision, and repeated valid appeals append further events while leaving the
status `under_review`. Neither the scores nor the original decision entry is
overwritten.

Errors use the same `error`/`message` shape: **400** with `invalid_request` for
an invalid body or missing, wrongly typed, or blank required strings. **404**
with `content_not_found` if no original decision matches `content_id`.


---

## Signals and Scoring

<!-- For each signal: what property it measures, why that might differ between
     human and AI writing, and WHAT IT CAN'T SEE.

     The blind spot is not optional. If you can't name it you don't understand
     the signal yet — and unit 8's attack set is built out of blind spots. -->

### Signal one — the model signal

**What it measures:** `detector.py::model_signal` uses the local language
model's perplexity: how surprising the next tokens in the submitted writing
are to that model. Lower perplexity becomes a higher AI-likeness score. It is
a predictability measurement, not an explanation of the writer's reasoning.

**Why that might differ between human and AI writing:** Generated writing may
favor likely word sequences, making it easier for a language model to predict.
Human writing can contain less expected word choices and turns of phrase.
This is a hypothesis behind the signal, not a rule separating all writers.

**What it can't see:** It has no drafts, revision history, or direct evidence
of who wrote the text. Plain human writing can be predictable and receive a
high score. Unusual vocabulary or edits to AI writing can make it less
predictable and lower the score. The starter also truncates the model input
to 400 tokens, so it cannot assess changes beyond that window.

### Signal two — the style signal

**What it measures:** Milestone 4's initial design measures sentence-length
variation (`sentence_length_spread`), vocabulary variety (`type_token_ratio`),
and punctuation density. The style score uses the first two, punctuation is
reported for diagnosis without assuming that more punctuation identifies AI.

**Style rule, written before implementation:** Count words in each nonempty
sentence. Sentence spread is population standard deviation divided by mean
sentence length. Convert it to `uniformity = 1 - min(spread, 1)`: zero spread
means perfectly uniform lengths; a spread of 1 means the standard deviation
equals the mean. Vocabulary variety is unique lowercase words divided by
total words; convert it to `repetition = 1 - type_token_ratio`.
Then `style_score = 0.5 * uniformity + 0.5 * repetition`, rounded to four
decimal places. Both components are bounded to 0–1 and higher means more
AI-like under these hypotheses. Fewer than two word-containing sentences
returns the neutral score `0.5`, because sentence variation is unavailable.
Raw empty-text vocabulary and punctuation ratios return zero without dividing
by zero. Punctuation density counts Unicode punctuation characters divided
by total characters, including whitespace. Curly apostrophes are normalized
for word counting. These are initial engineering heuristics, not learned
authorship boundaries.

**Why that might differ between human and AI writing:** Generated prose may
have more uniform sentence lengths and more repetitive wording, while human
writing may vary more. Punctuation offers another structural measurement,
but its useful direction needs checking rather than assuming that more or
less punctuation proves AI use.

**What it can't see:** These counts do not understand meaning or establish
authorship. A person can write uniformly, and someone can change an AI text's
score with typos, punctuation edits, quotations, or sentence splitting without
changing its substance. Type-token ratio also tends to decrease as text gets
longer, so length can masquerade as an authorship difference.

### The combining rule

<!-- Write the rule in words, then give the numbers. What happens when the two
     signals disagree? -->

**The rule, written before implementation:** The initial development
rule is `combined = 0.5 * model_score + 0.5 * style_score`, rounded to four
decimal places. Neither signal has earned greater trust. Giving them equal
weight makes opposite readings such as `0.9` and `0.1` produce `0.5`, rather
than allowing either signal alone to make a strong claim. This reduces the
influence of either signal when they disagree, but it cannot prevent false
accusations when both are wrong.

**The numbers:** Initial weights: model `0.5`, style `0.5`. The style
components also have equal weights of `0.5` each; these settings live in
`config.py`. Signal values must be finite and within 0–1, weights must be
finite, nonnegative, and sum to 1. Milestone 5 retains the initial cutoffs of
`0.35` and `0.65` and now maps the combined score to the exact labels below.
Confidence means the combined AI-likeness score, not a measured probability
of AI authorship.

**Where it lives:** `scoring.py::combine_signals`

<!-- ⚠️ The grader checks your code against that line. If your rule lives
     somewhere else, say where. -->

**A case where my two signals split, and what my rule does with it:** On the
lightly edited AI passage, the standalone model score was `0.6166` and the
style score was `0.3276`. Sentence spread was `0.3793103448275862` and
type-token ratio was `0.9655172413793104`: varied sentence lengths and almost
all-unique words lower this style heuristic despite the supplied AI origin.
The equal-weight arithmetic gives `0.4721`, inside the starter's unsure band.
Using `0.5` as a diagnostic midpoint, the signals lean in opposite directions,
this midpoint comparison is not a final label decision. Their disagreement
is a reason for caution, not evidence that editing made the writing human.
The original unedited AI passage was not supplied, so this is not a measured
before/after editing effect. Exact calibration output is under **Sample Run**.



---

## Label Variants

<!-- The exact text of all three labels, as a reader would see them, and the
     score range each covers.

     Write them for someone who has never heard the word "threshold". -->

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human | `0 <= score <= 0.35` | Our signals suggest this was probably written by a person. This assessment can be wrong. |
| unsure | `0.35 < score < 0.65` | Our signals cannot reliably tell whether this was written by a person or AI. This is not an accusation of AI use. You can request a review if you disagree. |
| high-confidence AI | `0.65 <= score <= 1` | Our signals suggest this text may be AI-generated. This assessment can be wrong. You can request a review if you disagree. |

**Why the unsure label is worded this way:** The uncertainty belongs to
the detection methods, not to the writer’s honesty. The label explicitly
avoids an accusation and offers a way to challenge the assessment.
It does not require the writer to understand a score or a cutoff.

These initial ranges retain `HUMAN_THRESHOLD = 0.35` and
`AI_THRESHOLD = 0.65` in `config.py`, no numerical cutoff was changed for
this milestone. The outer boundaries are inclusive and the middle is
strictly between them, so every valid score maps to exactly one label.
The assignment’s “high-confidence” variant names do not establish a
statistical confidence level or prove authorship. The wording remains
qualified because the signals can be wrong.

**Location:** `scoring.py::score_to_label`, `scoring.py::LABEL_TEXT`, and
`scoring.py::label_ranges`. Exact output of `label_ranges()`:

```text
high-confidence human: 0 <= score <= 0.35
unsure: 0.35 < score < 0.65
high-confidence AI: 0.65 <= score <= 1
```

---

## Sample Run

### Milestone 3 — one signal, development checks

The criteria were already committed at `3d4490b` before these checks.
At the Milestone 3 checkpoint, the route used only `detector.model_signal`:
`confidence` and `style_score` were `null`, `guess` was temporarily `unsure`,
and the label explicitly identified the model-only stage. The captured output
below preserves that checkpoint. The Milestone 4 section later in this sample
run documents the current route with both signals and a combined confidence.
Final labels and `/appeal` were added in Milestone 5, documented later in this sample run.

The server was run without the reloader for these checks:

```powershell
.venv\Scripts\python.exe -u -c "from app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
```

The model checks used the existing local cache with `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`; no model download was needed.

#### First: the hardcoded route answered before model wiring

**Claim:** The temporary hardcoded `/submit` handler returned HTTP 200
through curl before either signal was connected.
**Location:** The first implementation pass of `app.py::submit`, that body
was subsequently replaced by the model-only implementation.

Request file: `results/milestone3/route_check_request.json`:

```json
{"text":"This is a route check. The model is not connected yet.","creator_id":"milestone3_route_check"}
```

```powershell
curl.exe -sS --max-time 30 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone3/route_check_request.json'
```

Exact response:

```text
{"confidence":null,"content_id":"00000000-0000-0000-0000-000000000000","guess":"unsure","label":"Placeholder: route check only.","model_score":null,"status":"decided","style_score":null}

HTTP_STATUS=200
```

#### Standalone detector checks with the selected inputs

**Claim:** The original AI-generated input and the human-written
input both produced the genuine standalone outputs below.
**Location:** `detector.py::perplexity`, `detector.py::model_signal`, and
the CLI block in `detector.py`.

The exact inputs and source notes are saved in
[detector_inputs.json](results/milestone3/detector_inputs.json). The AI
paragraph was generated by Codex. I supplied the following passage and
identified it as human-written, it is used verbatim:

> Thus, I think it’s time for a level of accountability. Never did I imagine that I would live in a time that I would have to wonder if a human or computer wrote something. The time has come for those of us who are writers to fight back against the wave of imposter writers.

**Mixed/intermediate sample:**
The three-input standalone exercise is incomplete until sample is added.

The complete standalone commands, stdout, and stderr are preserved in
[standalone_detector.txt](results/milestone3/standalone_detector.txt).
Exact stdout from the two selected inputs:

**ai_generated**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     43.8
model_signal   0.5106   (higher = more likely AI)
```

**human_written**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     38.8
model_signal   0.5588   (higher = more likely AI)
```

The supplied human passage scored `0.5588`, slightly higher in AI-likeness
than the generated paragraph's `0.5106`. This is a signal limitation, not a
reason to change the known source of either input. These are development
checks, not accuracy estimates or formal criterion verdicts. No weights,
midpoint, or thresholds were tuned from these readings.

#### Real curl submissions and the saved audit entries

**Claim:** The two current `/submit` requests returned their standalone model
scores with distinct UUIDs, and `GET /log?limit=2` returned matching audit
entries. `/health` reported that the detector remained loaded.
**Location:** `app.py::submit`, `detector.py::model_signal`,
`audit.py::log_decision`, `audit.py::_append`, `app.py::get_log`, and
`app.py::health`.

The exact request bodies are saved as
[submit_ai_generated_request.json](results/milestone3/submit_ai_generated_request.json) and
[submit_human_written_request.json](results/milestone3/submit_human_written_request.json).
They contain the same selected texts as the standalone inputs, plus their
`creator_id` values. The commands below render the actual curl arguments in PowerShell
syntax, responses are pasted unchanged from captured stdout.

```text
CHECK: submit_ai_generated
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone3/submit_ai_generated_request.json'
{"confidence":null,"content_id":"6384c81c-095d-4218-b858-57e5721943a1","guess":"unsure","label":"Placeholder: model signal only; no authorship label yet.","model_score":0.5106,"status":"decided","style_score":null}

HTTP_STATUS=200

CHECK: submit_human_written
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone3/submit_human_written_request.json'
{"confidence":null,"content_id":"6111a423-63be-4f4d-84bf-6b4b1c764fff","guess":"unsure","label":"Placeholder: model signal only; no authorship label yet.","model_score":0.5588,"status":"decided","style_score":null}

HTTP_STATUS=200

CHECK: log
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' 'http://127.0.0.1:5000/log?limit=2'
{"count":2,"entries":[{"combined_score":null,"content_id":"6384c81c-095d-4218-b858-57e5721943a1","creator_id":"milestone3_ai_generated","guess":"unsure","label":"Placeholder: model signal only; no authorship label yet.","model_score":0.5106,"stage":"model_only","status":"decided","style_score":null,"timestamp":"2026-10-17T05:25:09+00:00"},{"combined_score":null,"content_id":"6111a423-63be-4f4d-84bf-6b4b1c764fff","creator_id":"milestone3_human_written","guess":"unsure","label":"Placeholder: model signal only; no authorship label yet.","model_score":0.5588,"stage":"model_only","status":"decided","style_score":null,"timestamp":"2026-10-17T05:25:09+00:00"}]}

HTTP_STATUS=200

CHECK: health
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' http://127.0.0.1:5000/health
{"detector_loaded":true,"detector_model":"gpt2","log_entries":5,"ok":true,"rate_limiting":false}

HTTP_STATUS=200

PASS: 2 current curl submissions matched standalone scores and their audit entries; the model stayed loaded.
```

The file written by the route is [logs/audit.jsonl](logs/audit.jsonl).
The current captured responses and complete HTTP transcript are saved in
[results/milestone3](results/milestone3). The append-only audit log retains
earlier development decision metadata, which contains no submitted text;
`limit=2` shows the two replacement-run decisions above. Entries include `stage: "model_only"` to distinguish them from
later combined scores. `status: "decided"` means the model-only result was
recorded, not that final authorship has been established.

**Appeal sample:** See the completed Milestone 5 sample below.

#### Focused route checks

**Claim:** Four tests passed with a mocked detector and temporary audit
files: score/identifier consistency, malformed-input rejection before
scoring, the exact character limit, and detector error handling.
**Location:** `tests/test_submit.py::SubmitTests`.

```text
$ .venv\Scripts\python.exe -m unittest discover -s tests -v
test_detector_failures_never_become_successful_decisions (test_submit.SubmitTests.test_detector_failures_never_become_successful_decisions) ... ok
test_exact_character_limit_is_accepted (test_submit.SubmitTests.test_exact_character_limit_is_accepted) ... ok
test_invalid_requests_are_rejected_before_the_model_runs (test_submit.SubmitTests.test_invalid_requests_are_rejected_before_the_model_runs) ... ok
test_score_and_identifiers_survive_response_and_audit_log (test_submit.SubmitTests.test_score_and_identifiers_survive_response_and_audit_log) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.032s

OK
```

These checks verify route behavior with a controlled model result. The curl
transcript above separately exercises the real model. Neither is a formal
verdict on the five acceptance criteria.

---

### Milestone 4 — both signals and combined confidence

**Claim:** The style signal ran on its own before route wiring. Both signals
were then run on the same three comparison inputs: the retained AI paragraph,
the human passage, and the lightly edited AI passage. The formal
human passage was the fourth calibration input. Four live curl submissions
subsequently returned those same scores and their equal-weight combination,
with matching audit entries.
**Location:** `stylometry.py::sentence_length_spread`,
`stylometry.py::type_token_ratio`, `stylometry.py::punctuation_density`,
`stylometry.py::style_signal`, `detector.py::model_signal`,
`scoring.py::combine_signals`, `app.py::submit`, and `audit.py::log_decision`.

The combining rule was written in **Signals and Scoring** before code changes.
The style components use `0.5` uniformity and `0.5` repetition. Model settings,
weights, and the unchanged starter label cutoffs are saved in
[config_snapshot.json](results/milestone4/config_snapshot.json).
These are development/calibration checks, not the formal evaluation of
`criteria.md`. No acceptance targets or thresholds were changed afterward.

All four exact texts and their source notes are saved in
[inputs.json](results/milestone4/inputs.json). The two new passages were used
verbatim, including the edited-AI line break and the formal passage's initial
word `merging`. Earlier withdrawn chat text was not reused. The edited AI
input now supplies a third comparison case. Its unedited original was not supplied, so this
is not a controlled measurement of editing's effect.

| Development input | Model score | Style score | Combined `confidence` |
|---|---|---|---|
| ai_generated | 0.5106 | 0.5489 | 0.5298 |
| human_written | 0.5588 | 0.4753 | 0.5171 |
| lightly_edited_ai | 0.6166 | 0.3276 | 0.4721 |
| formal_human | 0.6103 | 0.4500 | 0.5302 |

For the three comparison inputs, using `0.5` only as a diagnostic midpoint:
model and style both lean AI-like for `ai_generated`, they lean in opposite
directions for `human_written` and `lightly_edited_ai`. Their numerical
scores are the evidence, these midpoint descriptions are not final labels.
The edited AI case is the largest split, explained in **Signals and Scoring**.
The formal human case also splits: model `0.6103`, style `0.4500`, combined
`0.5302`. Formality did not make this particular human passage unpredictable
to GPT-2, the scores do not establish a general rule about formal writing.

All four combined scores are near the middle (`0.4721`–`0.5302`). Under the
unchanged starter cutoffs they would all fall in the unsure band. They do
not demonstrate label coverage or reliable separation by authorship.
The route still returns a temporary `guess: "unsure"` and an explicit
placeholder label until Milestone 5 implements final label mapping,
`confidence` is now the real combined AI-likeness score, not label certainty.

#### Exact standalone output

Each invocation's actual argument list, stdout, and stderr is saved in
[standalone_signals.txt](results/milestone4/standalone_signals.txt).
The following stdout is pasted from those runs:

**ai_generated — stylometry.py**

```text
7 sentences, 104 words

sentence_length_spread   0.25800784355766804
type_token_ratio         0.6442307692307693
punctuation_density      0.01485148514851485
style_signal             0.5489   (higher = more likely AI)

Style uses sentence uniformity and vocabulary repetition; punctuation is diagnostic only.
```

**ai_generated — detector.py**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     43.8
model_signal   0.5106   (higher = more likely AI)
```

**human_written — stylometry.py**

```text
3 sentences, 54 words

sentence_length_spread   0.32710225430843876
type_token_ratio         0.7222222222222222
punctuation_density      0.01838235294117647
style_signal             0.4753   (higher = more likely AI)

Style uses sentence uniformity and vocabulary repetition; punctuation is diagnostic only.
```

**human_written — detector.py**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     38.8
model_signal   0.5588   (higher = more likely AI)
```

**lightly_edited_ai — stylometry.py**

```text
2 sentences, 29 words

sentence_length_spread   0.3793103448275862
type_token_ratio         0.9655172413793104
punctuation_density      0.031088082901554404
style_signal             0.3276   (higher = more likely AI)

Style uses sentence uniformity and vocabulary repetition; punctuation is diagnostic only.
```

**lightly_edited_ai — detector.py**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     33.4
model_signal   0.6166   (higher = more likely AI)
```

**formal_human — stylometry.py**

```text
2 sentences, 40 words

sentence_length_spread   0.15
type_token_ratio         0.95
punctuation_density      0.023333333333333334
style_signal             0.45   (higher = more likely AI)

Style uses sentence uniformity and vocabulary repetition; punctuation is diagnostic only.
```

**formal_human — detector.py**

```text
Loading gpt2 (first run downloads ~550 MB)…
perplexity     34.0
model_signal   0.6103   (higher = more likely AI)
```

#### Exact live HTTP output and audit records

The curl request files are saved beside this transcript in
[results/milestone4](results/milestone4). They contain the texts from
`inputs.json` and the creator IDs shown in the audit entries. The loopback
server used the same no-reloader command as Milestone 3 and the existing
cached model in offline mode.

```text
CHECK: submit_ai_generated
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone4/submit_ai_generated_request.json'
{"confidence":0.5298,"content_id":"4b0829a4-657a-4dcc-91d0-386207565bac","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.5106,"status":"decided","style_score":0.5489}

HTTP_STATUS=200

CHECK: submit_human_written
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone4/submit_human_written_request.json'
{"confidence":0.5171,"content_id":"2504b041-8cdd-4484-a5a7-395bfe8bd175","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.5588,"status":"decided","style_score":0.4753}

HTTP_STATUS=200

CHECK: submit_lightly_edited_ai
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone4/submit_lightly_edited_ai_request.json'
{"confidence":0.4721,"content_id":"3d7eedc9-f883-433b-8b32-c1a8a330e15c","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.6166,"status":"decided","style_score":0.3276}

HTTP_STATUS=200

CHECK: submit_formal_human
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone4/submit_formal_human_request.json'
{"confidence":0.5302,"content_id":"02971b64-01d6-412e-afef-a61a74996c8e","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.6103,"status":"decided","style_score":0.45}

HTTP_STATUS=200

CHECK: log
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' 'http://127.0.0.1:5000/log?limit=4'
{"count":4,"entries":[{"combined_score":0.5298,"content_id":"4b0829a4-657a-4dcc-91d0-386207565bac","creator_id":"milestone4_ai_generated","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.5106,"stage":"combined_signals","status":"decided","style_score":0.5489,"timestamp":"2026-10-17T05:44:30+00:00"},{"combined_score":0.5171,"content_id":"2504b041-8cdd-4484-a5a7-395bfe8bd175","creator_id":"milestone4_human_written","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.5588,"stage":"combined_signals","status":"decided","style_score":0.4753,"timestamp":"2026-10-17T05:44:30+00:00"},{"combined_score":0.4721,"content_id":"3d7eedc9-f883-433b-8b32-c1a8a330e15c","creator_id":"milestone4_lightly_edited_ai","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.6166,"stage":"combined_signals","status":"decided","style_score":0.3276,"timestamp":"2026-10-17T05:44:30+00:00"},{"combined_score":0.5302,"content_id":"02971b64-01d6-412e-afef-a61a74996c8e","creator_id":"milestone4_formal_human","guess":"unsure","label":"Placeholder: both signals scored; authorship labels pending.","model_score":0.6103,"stage":"combined_signals","status":"decided","style_score":0.45,"timestamp":"2026-10-17T05:44:30+00:00"}]}

HTTP_STATUS=200

CHECK: health
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' http://127.0.0.1:5000/health
{"detector_loaded":true,"detector_model":"gpt2","log_entries":9,"ok":true,"rate_limiting":false}

HTTP_STATUS=200

PASS: 4 real submissions matched standalone model/style scores and their combined-score audit records.
```

The append-only [audit log](logs/audit.jsonl) retains earlier model-only
entries and adds these four with `stage: "combined_signals"`. Each new entry
contains `model_score`, `style_score`, and `combined_score`; the last equals
the response's `confidence`. Raw readings are preserved before aggregation in
[signal_readings.json](results/milestone4/signal_readings.json), and the live
response values plus features are in
[calibration_results.json](results/milestone4/calibration_results.json).

#### Focused tests

**Claim:** Twelve tests passed for feature direction and sparse input, scoring
bounds and invalid weights, and route-to-audit consistency of both scores and
combined confidence. The route tests mock the signals, the curl checks above
separately exercise the real signals.
**Location:** `tests/test_stylometry.py::StylometryTests`,
`tests/test_scoring.py::ScoringTests`, and `tests/test_submit.py::SubmitTests`.

Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Exact summary excerpt from the test run:

```text
----------------------------------------------------------------------
Ran 12 tests in 0.034s

OK
```

---

### Milestone 5 — reader labels and appeal path

**Claim:** Three real `/submit` calls reached all three labels using the
unchanged initial ranges. The supplied human passage was then appealed using
its returned `content_id`. `/appeal` confirmed `under_review`, and `GET /log`
showed the appended event with the original decision preserved.
**Location:** `scoring.py::score_to_label`, `scoring.py::label_ranges`,
`app.py::submit`, `app.py::appeal`, `audit.py::entries_for`,
`audit.py::log_appeal`, and `app.py::get_log`.

The exact texts and source notes are saved in
[inputs.json](results/milestone5/inputs.json). The human input is the human passage, used verbatim. The other two are deliberately constructed
AI-generated development probe, fiction with uneven sentence lengths and
unusual vocabulary, and a repeated simple sentence. They demonstrate label
reachability, not classifier accuracy. They are separate from the fixed
formal evaluation samples in `criteria.md`.

| Development input | Actual source | Model score | Style score | Combined score | Returned guess |
|---|---|---|---|---|---|
| varied_fiction_probe | AI-generated probe | 0.0955 | 0.0119 | 0.0537 | `human` |
| supplied_human | Supplied as human-written | 0.5588 | 0.4753 | 0.5171 | `unsure` |
| repetitive_ai_probe | AI-generated probe | 0.9947 | 0.9583 | 0.9765 | `ai` |

The fiction probe is a **false negative**: AI-generated text received the
human label. The original four calibration inputs still fall in the middle
band. No cutoffs, signal weights, or scoring features were changed to turn
these development checks into an accuracy claim or a formal criterion pass.

The appeal explanation below is explicitly a development-check request,
not a fabricated account of the writer’s drafting history. Exact request body:

```json
{
  "content_id": "0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8",
  "reasoning": "Milestone 5 development check: please review the assessment of this supplied human-written passage."
}
```

The original entry was saved immediately before the appeal in
[appealed_original_before.json](results/milestone5/appealed_original_before.json):

```json
{
  "timestamp": "2026-10-17T06:05:12+00:00",
  "content_id": "0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8",
  "creator_id": "milestone5_supplied_human",
  "guess": "unsure",
  "model_score": 0.5588,
  "style_score": 0.4753,
  "combined_score": 0.5171,
  "label": "Our signals cannot reliably tell whether this was written by a person or AI. This is not an accusation of AI use. You can request a review if you disagree.",
  "status": "decided",
  "stage": "labeled"
}
```

The server ran with the same no-reloader command used in earlier milestones,
using the cached detector offline. The actual curl arguments are rendered in
PowerShell syntax below. Requests use saved UTF-8 JSON files; responses are
pasted unchanged from captured stdout.

```text
CHECK: submit_varied_fiction_probe
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone5/submit_varied_fiction_probe_request.json'
{"confidence":0.0537,"content_id":"19f3b20e-822a-4afa-938c-0814af751bbc","guess":"human","label":"Our signals suggest this was probably written by a person. This assessment can be wrong.","model_score":0.0955,"status":"decided","style_score":0.0119}

HTTP_STATUS=200

CHECK: submit_supplied_human
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone5/submit_supplied_human_request.json'
{"confidence":0.5171,"content_id":"0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8","guess":"unsure","label":"Our signals cannot reliably tell whether this was written by a person or AI. This is not an accusation of AI use. You can request a review if you disagree.","model_score":0.5588,"status":"decided","style_score":0.4753}

HTTP_STATUS=200

CHECK: submit_repetitive_ai_probe
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/submit -H 'Content-Type: application/json' --data-binary '@results/milestone5/submit_repetitive_ai_probe_request.json'
{"confidence":0.9765,"content_id":"22e00082-32ff-4e6b-bdb5-3ccb07ca0d45","guess":"ai","label":"Our signals suggest this text may be AI-generated. This assessment can be wrong. You can request a review if you disagree.","model_score":0.9947,"status":"decided","style_score":0.9583}

HTTP_STATUS=200

CHECK: appeal
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://127.0.0.1:5000/appeal -H 'Content-Type: application/json' --data-binary '@results/milestone5/appeal_request.json'
{"content_id":"0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8","message":"Your appeal has been recorded. The submission is under review.","status":"under_review"}

HTTP_STATUS=200

CHECK: log
$ curl.exe -sS --max-time 90 -w '\nHTTP_STATUS=%{http_code}\n' 'http://127.0.0.1:5000/log?limit=4'
{"count":4,"entries":[{"combined_score":0.0537,"content_id":"19f3b20e-822a-4afa-938c-0814af751bbc","creator_id":"milestone5_varied_fiction_probe","guess":"human","label":"Our signals suggest this was probably written by a person. This assessment can be wrong.","model_score":0.0955,"stage":"labeled","status":"decided","style_score":0.0119,"timestamp":"2026-10-17T06:05:12+00:00"},{"combined_score":0.5171,"content_id":"0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8","creator_id":"milestone5_supplied_human","guess":"unsure","label":"Our signals cannot reliably tell whether this was written by a person or AI. This is not an accusation of AI use. You can request a review if you disagree.","model_score":0.5588,"stage":"labeled","status":"decided","style_score":0.4753,"timestamp":"2026-10-17T06:05:12+00:00"},{"combined_score":0.9765,"content_id":"22e00082-32ff-4e6b-bdb5-3ccb07ca0d45","creator_id":"milestone5_repetitive_ai_probe","guess":"ai","label":"Our signals suggest this text may be AI-generated. This assessment can be wrong. You can request a review if you disagree.","model_score":0.9947,"stage":"labeled","status":"decided","style_score":0.9583,"timestamp":"2026-10-17T06:05:13+00:00"},{"content_id":"0dfcb25f-0c7a-49d8-9fa3-416384d0aaf8","creator_id":"milestone5_supplied_human","event":"appeal","reasoning":"Milestone 5 development check: please review the assessment of this supplied human-written passage.","status":"under_review","timestamp":"2026-10-17T06:05:13+00:00"}]}

HTTP_STATUS=200

PASS: all 3 labels reached with real text; a real submission was appealed, the log shows under_review, and prior audit records are unchanged.
```

The original entry still says `decided`. The later `appeal` event for the same
`content_id` says `under_review` and represents the new status. The log is
append-only: an appeal preserves the original scores, guess, label, creator,
and timestamp. The response confirms receipt of the appeal; this project does
not implement a reviewer, an automatic recheck, or an appeal-resolution step.

All request/response files, the range output, and the weights/cutoffs snapshot
are saved in [results/milestone5](results/milestone5). The audit entries are in
[logs/audit.jsonl](logs/audit.jsonl). These are development checks, not the
three-trial formal acceptance evaluation.

#### Focused label and appeal tests

**Claim:** Eighteen tests passed, including exact cutoff boundaries, rejection
of invalid scores, label propagation into responses and decision logs, valid
and repeated appeals, malformed request rejection, unknown IDs, and keeping
the original decision intact. The appeal tests use real temporary audit files,
no existing project log entries are modified by those tests.
**Location:** `tests/test_scoring.py::ScoringTests`,
`tests/test_submit.py::SubmitTests`, and `tests/test_appeal.py::AppealTests`.

Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Exact summary excerpt:

```text
----------------------------------------------------------------------
Ran 18 tests in 0.068s

OK
```

---

## How I Used AI

**Moment 1**

- *What I asked for:* Help choosing development examples to run through the
  detector and comparing AI-generated and human-written text.
- *What came back:* AI supplied AI-generated passages and development
  probes. It also initially reused an excerpt from my earlier chat explanation
  as the human example and used that excerpt in a mixed example. Those were
  not the human test passages I had selected.
- *What I changed:* I asked AI to remove the chat-derived sample text and
  supplied the human passage I wanted to use. I later supplied formal human
  writing and lightly edited AI text for the four-input calibration check.
  The replacement passages were used verbatim, and the replacement runs were
  recorded separately from the original development sequence.
- *How it was checked:* AI reran the supplied human passage through the
  standalone detector and `/submit`, then refreshed the requests, responses,
  and README evidence. The selected inputs and source notes are saved in
  `results/milestone3/detector_inputs.json` and
  `results/milestone4/inputs.json`. The withdrawn chat text is not retained in
  those sample files or their command transcripts. Earlier audit entries
  contain decision metadata rather than the submitted text.

**Moment 2**

- *What I asked for:* Help designing the endpoint contracts and the steps a
  submission and appeal should follow, then help with their initial
  implementation.
- *What came back:* AI helped turn the flow we discussed into request
  validation, signal calls, score combination, label mapping, audit logging,
  and an appeal linked by `content_id`. It also proposed and created separate
  test modules for the endpoints and scoring behavior.
- *What I changed:* I kept the endpoint flow we designed together and retained
  the separate test modules. I chose equal starting weights for the two signals
  and a 20,000-character input maximum. AI wrote the initial implementation
  and tests.
- *How it was checked:* AI ran the focused tests and real curl requests.
  The saved Milestone 5 run shows all three labels reached through `/submit`
  and a real appeal confirmed as `under_review` in `/log`, with the original
  decision unchanged. The tests are in `tests/test_submit.py`,
  `tests/test_appeal.py`, `tests/test_scoring.py`, and `tests/test_stylometry.py`.
  The requests and responses are preserved under **Sample Run** and in
  `results/milestone5/`. One AI-generated probe received the human label, so
  these checks establish working routes and reachable labels rather than
  reliable authorship detection.

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
