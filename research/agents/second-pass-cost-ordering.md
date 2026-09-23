# Second pass: quiet ordering by prospective search cost

Baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`; 20 September 2026. **Decision: go for an inexpensive frozen shadow diagnostic; no production patch or strength test yet.** This investigation changes no engine source and is independent of pawn-history LMR and duplicate-SEE work.

## Mechanism and limits of the objective

At a non-PV expected-cut node, the useful question is often “which move can establish the required lower bound most cheaply?” rather than “which move has the highest absolute value?” In a simplified two-move model with fixed costs `cA,cB`, independent outcomes, and cutoff probabilities `pA,pB`, expected cost of A then B is `cA+(1-pA)cB`; B then A is `cB+(1-pB)cA`. A goes first exactly when `pA/cA >= pB/cB`. Equivalent pairwise exchange reasoning applies to a sequence under the same assumptions.

This is an explanatory objective, not a theorem about Stockfish. Costs and success probabilities depend on move order, reductions, history, TT contents, and the evolving tree. Existing histories are bounded online heuristic scores, not calibrated probabilities. Dividing the current signed move score by node count would be unjustified, particularly when scores cross zero.

The baseline records root-move node effort and uses it in root score averages and time management. Internal moves only initialize the current `nodeCount` for root nodes; their subtree costs are not retained in a dedicated cost predictor. Internal history updates depend on success, depth, move order, TT status, and earlier statistics. These can indirectly encode cost, so absence of an explicit cost table is not absence of cost information. See the pinned [search implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp) and [history update rule](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/history.h).

## One bounded feature and action to diagnose

Prospective feature: **expected node cost of the naturally first good quiet, conditional on it actually being searched**, keyed by `(piece type, side-relative destination, parent depth)` at non-PV expected-cut nodes. Piece colors share a canonical destination through rank reflection; source square and pawn structure are deliberately omitted in this first narrow hypothesis. The estimate is learned only from prior first-good-quiet attempts in the same role, not indiscriminately from later and more heavily reduced moves. Record complete cost from before `do_move` through all re-searches, without treating aborted searches as completed observations. Record pruned-first-quiet events separately rather than silently conflating them with cheap searched moves.

Illustrative frozen action: after the normal good-capture stage and normal quiet scoring, consider swapping only the first two good quiets when all these hold:

- Non-PV, `cutNode`, not in check, not an excluded search, parent depth 6–9.
- Both moves already qualify as good quiets; their existing move scores differ by at most 256.
- Each cost cell has at least 16 prior samples and predicts the second move costs at most half as much as the first.

No crossing capture/quiet stage boundaries, no pruned-move rescue, no change to a score, history update, LMR formula, or evaluation. The swap naturally changes moveCount and therefore LMR; this interaction is part of the intervention and must be measured, not denied.

**Depth 6–9, score gap 256, sample count 16, and a twofold cost gap are arbitrary research-design limits, not established optimal values.** They provide one precisely stated bounded rule whose coverage can be observed; do not tune them to whichever held-out outcomes look favorable. If coverage is negligible, this rule is not ready for implementation. A later independently designed rule would require a new stated hypothesis and validation sample.

For the shadow diagnostic, use offline arithmetic means and counts on the discovery corpus, freeze them before validation, and include uncapped node costs. A future online table could hold a count plus mean in at most roughly 12 KiB per worker for six piece types, 64 destinations, and four depth values. Exact update/decay policy remains unresolved and should not be invented before the feature demonstrates predictive value. Therefore the frozen rule is a diagnostic specification, not a ready-to-submit production implementation.

## Confounds that can reverse the apparent benefit

1. **Censoring:** the second move's result is unknown whenever the first move cuts off. Evaluating only pairs where both were searched selects first-move failures. A high apparent success rate for the second move in that subset is not evidence that it should go first.
2. **Baseline selection:** first-good-quiet training labels reduce variation in search role but are still conditional on baseline ordering. Applying that predictor to a move naturally ranked second is a distribution shift. It does not solve off-policy estimation.
3. **Depth and order:** cheap later searches may simply be reduced searches. Moving a move earlier changes its cost and reliability. Even first-quiet cost changes with preceding capture count, correction, TT/PV status, history score, and previous search results.
4. **Expensive successes matter:** a long tactical proof can be the only winning continuation. Favoring cheap but unsuccessful moves loses both time and search depth. Near-equal history scores are not proof of equal cutoff probability.
5. **Costs are stateful:** earlier searches warm TT entries and update histories. Child costs are heavy-tailed and strongly position-dependent; averaging unrelated moves with the same piece/destination can destroy the signal. Node count is also an imperfect proxy for time because evaluation and move generation costs vary.
6. **Sparse data and overhead:** a new table needs warmup, reads, writes, and cache capacity. Low intervention incidence or redundancy with current history can cost more than it saves. The failed singular-witness proposal demonstrated this risk directly.

## Cheap frozen diagnostic and decision criteria

Use a logging-only baseline with unchanged decisions and verified bench/iteration traces. Before collecting outcomes, choose discovery and held-out **positions/games** and fixed budgets. At each qualifying node, log the first two good-quiet identities and their scores, the predictor's inputs available before either search, parent context, actual initial child depths, and each move's eventual searched/pruned/unreached status. Log every first-good-quiet attempt's completed node cost and actual beta-cutoff outcome. No additional child search is needed for this stage.

Fit the declared cost means on discovery positions only. Freeze the mapping, counts, and rule; then compute held-out prospective proposals without adapting to their outcomes. Report:

- Full density funnel: qualifying nodes, two good quiets, near-score ties, supported cells, predicted twofold gaps, and proposals per million nodes/position. Include cold/missing cells.
- Held-out cost-prediction error on naturally first good quiets that are searched, compared with a parent-depth-only mean and the existing score/context predictors. This asks whether the new feature contributes information, not whether sorting by it wins.
- Actual first-move cutoff frequency and its relation to predicted cost. Success probability is a separate target from cost; lower-cost groups that also lose cutoff probability can be worse under `p/c`.
- Proposal outcomes with a separate explicit **unknown second-move outcome** category. Never assign zero cost, zero success, or inferred success to censored moves. Report later-move labels descriptively only.
- Full distributions and position-level variation; confidence intervals, if calculated, resample positions/games rather than treating millions of correlated search nodes as independent trials.

Reject if support is sparse, cost prediction adds little beyond depth/history, or the low-cost signal mostly identifies low success. Even a positive shadow result does not establish causal savings. It would justify a single bounded implementation experiment on a fresh position set, followed by a fixed local screen and standard independent strength testing. It cannot justify an Elo claim. A robust causal comparison would need actual changed-order runs or expensive isolated state snapshots; replaying a FEN alone does not restore the original TT, histories, or path.

## Prior art and scope

The cheap-cutoff objective is longstanding. Plaat, Schaeffer, Pijls, and de Bruin's [SSS* = Alpha-Beta + TT technical report](https://webdocs.cs.ualberta.ca/~jonathan/publications/ai_publications/tr94-17.pdf) discusses distinct cutoff moves producing different-sized proof trees and the difficulty of knowing which is cheapest. The proposal is an application of an old objective to the current engine, not a new search principle.

Stockfish's accepted [dynamic root-score effort weighting](https://github.com/official-stockfish/Stockfish/commit/93ed4b53c4f602c4cc41dbdb67961a2a4712c60b) confirms that effort already matters elsewhere in this baseline. Root weighting is not evidence for internal cost-based ordering. Local commit-message searches for cost, effort, subtree, and node-count/history interactions found root/time-management changes and nearby allocation changes, but no matching accepted internal quiet-cost table. This bounded search does not establish novelty or rule out prior failed trials.

Source inspected: `history.h` history types and saturation update; `search.cpp` current root effort, move loop, internal LMR/re-search and history updates; current move-picker stage/score machinery; local history and the cited primary research. No code was changed or test submitted. The strongest current conclusion is that this is a reasonable **information-value diagnostic**, not yet a strong improving upgrade.
