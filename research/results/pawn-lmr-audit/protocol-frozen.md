# Pawn-context allocation: a causal root-prefix audit

Baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`; unchanged network. Protocol fixed before collecting the new seed-20260921 corpus. This is a diagnostic design, not an engine upgrade or an Elo claim. No reduction coefficient, learned predictor, or production policy is selected.

## The specific missing evidence

Pawn-structure history already affects quiet ordering and shallow pruning. It does not enter the final LMR `statScore`, which blends main and two continuation histories. The earlier 64-root observation showed a weak exploratory association between pawn-history sign and survival of **already selected reduced fail-highs**, conditional on coarse existing features. It did not observe the quiet moves whose reduced searches failed low but whose deeper searches would have changed the threshold decision. Those censored outcomes are the relevant uncertainty if we intend to protect promising moves from excessive reduction.

The hypothesis to test is narrow: among otherwise comparable late quiet scouts with nonpositive current `statScore`, positive pawn-context history identifies more baseline fail-lows that would become **verification-supported threshold improvements** with one extra scout ply, at an acceptable additional search cost. Even a positive result would only motivate an isolated policy experiment. More search can always uncover some different answers; the required result is better targeting than matched controls, not merely finding illustrative rescues.

## Why replay the entire root prefix

A fresh FEN at the target node cannot reproduce its TT contents, learned histories, reduction context, repetition path, ancestor static evaluations or accumulated node-dependent draw behavior. Running the baseline scout and then a deeper scout sequentially also warms the TT and changes histories, so their states differ.

Instead, each root is initialized identically in a fresh single-thread process of **the same instrumented binary**. The discovery run executes baseline behavior and records candidate events. A treatment run repeats the entire deterministic root search until one selected event, verifies its identity and prefix digest, and then changes only that event's scout depth. Its prefix has therefore rebuilt the same relevant search state naturally. No altered search takes place before the target.

Use `Threads=1`, `Hash=16`, identical `ucinewgame`/position setup, unchanged network and `go depth 13`, with no time/node stopping. The root command uses the original FEN and any prescribed root history, never a child FEN. One event is perturbed per process. A failed identity check invalidates that run; it must never silently choose another event.

## Frozen sample and eligibility

1. Sample 64 distinct UHO FENs using seed **20260921**, excluding every exact FEN in the previously analyzed seed-20260920 corpus. Retain the book hash, sampled line indices and complete FEN manifest.
2. Run 64 baseline discovery searches with full iteration trace comparisons against the unmodified baseline. Require unchanged standard bench **1648567** before causal replay.
3. Number all LMR scout events chronologically before recursion, across the iterative root search. Candidate eligibility is: quiet move; non-root, non-PV, non-check, non-excluded parent; parent depth at least 6; `statScore <= 0`; original actual reduction `newDepth - d >= 2`; finite non-decisive window/results; completed original scout result `<= alpha`.
4. Split candidate events by **pre-move parent** pawn-history entry: positive versus nonpositive. The existing parent structure entry must be read before `do_move`, not from the child's pawn structure. Checking quiet moves remain eligible because the check restriction applies to the parent; log `givesCheck` separately and read the parent pawn entry even if the ordinary non-checking-quiet pruning path did not need it.
5. For each root, seek a common matching bucket across both signs. Fixed buckets are parent depth **6–7 / 8–9 / 10–11 / 12+**; original scout `d` **1–2 / 3–4 / 5+**; move count **2–3 / 4–7 / 8+**; and the exact `cutNode` boolean. The node type and all eligibility predicates are already held fixed.
6. If several common buckets exist, choose the minimum SHA-256 of `(seed, root identity, bucket)`. Within that bucket choose one event per pawn sign by the minimum SHA-256 of `(seed, root identity, event identity)`.
7. Roots lacking a common bucket produce no treatment replay. Preserve their pools and report that loss of coverage. Do not broaden bins or add unmatched fallback samples after seeing counts.
8. Publish the complete target-selection manifest before starting treatment replays. At most two selected events per root means **at most 128 treatment replays**, plus the 64 baseline discovery searches. The recorded discovery event supplies each treatment's baseline comparator; no extra baseline replay is required.

Baseline fail-low is intentionally used to define the audit population. No deeper treatment outcome participates in selection. The earlier corpus was used to formulate this hypothesis; it must not be re-described as a confirmatory holdout.

## Exact intervention

At the selected first reduced search, change its effective scout depth from `d` to `d+1`. Set `ss->reduction = newDepth - effectiveD` consistently, because the child uses this field for hindsight depth adjustment. Use `effectiveD` consistently in the existing post-scout comparisons governing optional extra depth and whether further verification is needed. The precondition `newDepth-d >= 2` ensures the treatment remains a reduced scout. This is one **nominal** scout-depth increment: changing `ss->reduction` can cross the child's existing hindsight-adjustment thresholds, so the realized tree need not be exactly one ply deeper. That interaction is part of a faithful reduction intervention, not a reason to leave the reduction field inconsistent.

All existing subsequent policy stays active: if the deeper scout now fails high, the normal depth-adjustment and full-depth verification logic runs; its result determines the eventual move value and ordinary updates. Do not simply treat the first deeper fail-high as success. Keep the existing continuation bonus, final history updates, TT writes, pruning, PV handling, and root time policy unchanged. There is no second selected event later in the same treatment run.

This measures a prospective one-ply reduction change at one event. It does **not** measure the runtime of a future conditional rescue policy that first runs `d` and, after seeing fail-low, reruns `d+1` in the already modified state. Such a policy would need its own audit of the actual two-search sequence. Do not transfer the present cost estimate to it silently.

## Event identity and reproducibility checks

At every scout entry, feed a canonical snapshot into a deterministic rolling prefix digest. At the selected event require the discovery ordinal, prefix digest and full entry record to match before perturbation. Record at least:

- Root/corpus identity, iteration root depth, event ordinal and ply.
- Parent position key, child position key after making the move, move encoding, parent pawn key, rule-50 and relevant repetition path identifiers.
- Parent alpha, beta, bestValue, static evaluation, working evaluation, depth, `newDepth`, original `d`, move count, cut/PV/parent-in-check/move-gives-check/excluded/capture status, TT move/value/depth/bound and correction value.
- Pre-scout `statScore`, main-history and continuation components used in it, and the pre-move parent pawn-history value.
- Node counter at entry, prefix digest, original reduction and proposed effective reduction.

Include only initialized meaningful fields in hashes, not object padding or pointer addresses. Pointer identity varies between processes. A full TT byte hash is unnecessary for this bounded single-thread replay and can itself hash unstable padding; determinism of the entire untouched prefix, exact entry checks and unchanged discovery traces provide the relevant check. This is a deterministic replay argument, not a claim that the fingerprint alone proves arbitrary hidden states equal.

If independent process discovery differs from the baseline at any iteration, or a target fingerprint differs, stop and diagnose. Report invalid runs distinctly and retain their logs. Do not average them into treatment results or replace them with easier events.

## Outcomes and honest interpretation

For both the discovery event and treatment record the original/deeper scout score, whether ordinary verification ran and at what depth, its result, the final move value at the unchanged parent threshold, and separate scout/verification/total-move node deltas. Save the complete resulting root trace, final best move/score and total root nodes. Keep every selected outcome.

Classify treatments as:

- **Still fail-low:** the extra scout ply never beats alpha.
- **Exposed illusion:** the extra scout ply beats alpha but normal verification returns to/below alpha.
- **Verification-supported recovery:** an additional ordinary verification actually ran and its final move result remains above alpha; at these non-PV nodes this is a cutoff at beta.
- **Accepted without further verification:** the deeper scout beats alpha but the existing depth-adjustment policy makes another verification unnecessary. This can occur when an original reduction of two becomes one and `doShallowerSearch` then lowers `newDepth` to the treatment scout depth. Keep this distinct from verification-supported recovery.
- **Invalid/aborted:** mismatch, incomplete run or invalid scores; never a favorable result.

The verification-supported category is stronger evidence than a shallow score change but is still selective-search evidence, not objective chess truth. Record root decision changes separately. A same-depth larger tree or changed root best move does not establish stronger play.

Report paired positive-minus-nonpositive recovery indicators and cost differences within each root's matched bucket. Show the full root-level distribution, counts and approximate root-level uncertainty; do not treat recursive events as independent samples. Both treatments are compared with their own identical-prefix baseline, while the two sign groups are only coarsely matched contexts. Their difference is therefore evidence about targeting, not a randomized causal effect of pawn-history sign. Coarse matching can leave residual confounding.

Immediate move costs are local, disjoint within that one invocation; aggregate nested event costs would overlap, but only one selected event per replay is being treated. Whole-root cost captures downstream adaptation and may increase or decrease for reasons beyond that move. Neither is elapsed-time evidence.

A useful result must show enough verification-supported recoveries, a consistent advantage for positive pawn history over matched controls, and tolerable costs without a concentration of tactical illusions. If the sample is sparse or sign advantage is inconsistent, report insufficiency rather than manufacture a production coefficient. Only subsequent independently validated policy experiments and completed STC/LTC matches can establish Elo.
