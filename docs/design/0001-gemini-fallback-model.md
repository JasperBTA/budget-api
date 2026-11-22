# 0001 — Fallback model for the Gemini PR review

Status: approved 2026-11-22 · implemented in `feat/gemini-fallback`

## 1. Goal and context

The advisory PR review (`scripts/ai_review.py`, `.github/workflows/ai-review.yml`) calls one model,
`gemini-4-hydrogen`, with 4 attempts and 10/20/40 s backoff. On 2026-11-22 it posted a review on
1 of 5 pull requests: PR #1 (after retries); PRs #2, #3, #4 and one re-run were skipped with
`503 UNAVAILABLE` ("high demand") or `504 DEADLINE_EXCEEDED`. An advisory reviewer that is
skipped 80% of the time is a dead element of the process. Goal: when the primary model fails,
try a second free-tier model before skipping, so most PRs get a review.

## 2. Scope

In:
- an ordered list of models in `scripts/ai_review.py`, tried one after another;
- which errors move on to the next model, and which skip at once;
- the review header names the model that actually answered;
- tests for the fallback order and the error rules; README update.

Out:
- paid models or enabling billing;
- making the review a required check (it stays advisory);
- caching reviews or skipping re-reviews on push (separate topic).

## 3. Proposed change

`scripts/ai_review.py`:

- Replace `DEFAULT_MODEL` with `DEFAULT_MODELS = ("gemini-4-hydrogen", "gemini-3.5-flash-lite")`.
  The environment variable `GEMINI_MODELS` (comma-separated) overrides it, so a model id can be
  changed in the workflow without a code change. `GEMINI_MODEL` is dropped (unused today).
- `main()` loops over the models. For each one it calls `ask_gemini()` (unchanged, SDK retries
  inside). The next model is tried when the call ends with:
  - an API error with code 404 (unknown model id), 408, 429 or 5xx;
  - a network error or timeout from the HTTP client.
  Any other failure (400 bad request, 401/403 key problem, invalid JSON answer) skips at once:
  a second model would not fix it.
- Attempts per model: 4 → 3 (backoff 10/20 s), so two models fit the job time.
  Worst case: 2 models × 3 attempts × 90 s timeout + ~62 s backoff ≈ 10 min, inside
  `timeout-minutes: 15` with room for job setup. Typical failure (fast 503s): about 1 minute.
  (Changed during implementation: the per-call timeout went from 120 s to 90 s after review
  measured the 120 s worst case at ~13 min, leaving too little margin.)
- The review header already prints the model name; it becomes the model that answered.
  The job summary lists each model tried and its error, e.g.
  `gemini-4-hydrogen: ServerError: 503 UNAVAILABLE … → gemini-3.5-flash-lite: answered`.
- An empty `GEMINI_MODELS` falls back to the default list.

`README.md`: the AI review section names both models and the fallback rule.

No database, API or migration changes. No new dependency.

## 4. Alternatives and decisions

| Decision | Choice | Rejected | Why |
| --- | --- | --- | --- |
| How to get a review more often | Second model after the first fails | More retries on one model; scheduled re-runs | 4 attempts over ~70 s already failed; a re-run later adds a workflow and still depends on one model |
| Fallback model | `gemini-3.5-flash-lite` | Another Flash or Pro model | Sources agree Flash-Lite is on the free tier with the highest daily limits (reported 500/day vs 20/day for Flash); Pro is reported paid-only since April 2026 |
| Where the list lives | Constant in the script, overridable by `GEMINI_MODELS` | Repository variable only; hard-coded only | Works with no setup on a fork, yet a wrong id is fixed with a one-line workflow change |
| Which errors fall through | 404, 408, 429, 5xx, network/timeout | Every error | 401/403/400 and invalid JSON mean the request or key is wrong; trying another model only burns quota |
| Two models in parallel | No, sequential | Ask both, keep the first answer | Doubles quota use on every PR; sequential costs the second call only when needed |

## 5. Risks and costs

| Risk | Effect | Mitigation |
| --- | --- | --- |
| The model id `gemini-3.5-flash-lite` is wrong (ids are not confirmed from official docs) | Fallback returns 404 every time | 404 falls through to a clean skip, never a failure; the job summary shows the 404; fix with `GEMINI_MODELS` in the workflow. Acceptance criterion below checks it on the first PR |
| Flash-Lite reviews are weaker | More missed findings or false alarms | The header names the model, so a reader knows which one reviewed; CI stays the gate |
| Free-tier daily limit (reported 20/day for Flash) | 429 on busy days | 429 falls through to the second model; both exhausted means a skip, as today |
| Longer jobs when both models fail slowly | Up to ~14 min of runner time | Public repo: Actions minutes are free; the job never blocks merge |
| Cost | — | $0: free tier only, billing stays disabled |

## 6. Rollout plan and acceptance criteria

One PR (`feat/gemini-fallback`): script, tests, README, this document.

- [ ] Unit tests (Gemini faked): the first model's 503 leads to the second model; a 404 also
      falls through; a 401 or an invalid JSON answer skips without trying the second model;
      both models failing ends in a skip with exit 0; the posted review names the model that
      answered.
- [ ] `GEMINI_MODELS="a,b"` overrides the default order (test).
- [ ] On the PR itself: the job summary shows which models were tried and what each returned.
- [ ] If the fallback id turns out wrong (404 in that summary), the PR fixes it before merge.
- [ ] Full check command green; reviewed by the `reviewer` subagent before the PR.

## 7. Open questions

1. **Fallback model id.** Sources name the free Flash-Lite model `gemini-3.5-flash-lite`, but no
   official page confirmed the id. Recommendation: use it, and let the first live run on this PR
   confirm it (a wrong id is a skip, not a failure).
2. **A third model?** Recommendation: no. Two cover an overloaded primary; a third mostly adds
   runner time. Revisit if skips stay above 1 in 3 PRs over the next week.
