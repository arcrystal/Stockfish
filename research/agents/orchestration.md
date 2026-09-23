# Stockfish Elo research: orchestration and decision record

Research baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3` (September 13, 2026). Personal fork: [arcrystal/Stockfish](https://github.com/arcrystal/Stockfish).

**20 September update:** all four submitted search candidates were rejected at STC. This initial ranking is historical. Read the [second-pass synthesis](second-pass-synthesis.md) and current ledger before continuing experiments. This document prioritizes hypotheses and records research coverage. Actual builds, candidate commits, matches, and Fishtest status are maintained by the lead agent in the [experiment ledger](../EXPERIMENTS.md).

**Historical first-pass conclusion (superseded):** suppressing negative correction-history updates from excluded-move searches is the strongest first experiment on causal reasoning and implementation cost. A 1,000-game local screen has not established a gain. The lead submitted the isolated candidate to [Fishtest](https://tests.stockfishchess.org/tests/view/6aa85960cb562be55c88e907); completed Fishtest evidence is still required before describing the candidate as stronger.

The research intentionally does not infer a rating increase from the number of agents, lines read, a changed benchmark signature, historical success of related patches, or a favorable small sample. Logical consistency can improve a heuristic's interpretation while making an empirically tuned engine weaker.

## Delegation and independent review

The user explicitly requested an orchestration agent and many deep idea investigations. The orchestration agent completed eight bounded investigations in four waves with two reusable researcher agents, alongside its own repository reading and the lead's builds/review. The concurrency limit was four agents including the lead and orchestrator, so eight investigations do not mean eight simultaneous agents. All eight reports were read and critically reviewed by the orchestrator.

| Wave | Search researcher | History researcher |
|---|---|---|
| 1 | Selective search calibrated by conflicting evidence | Reliability of correction-history training |
| 2 | TT bounds, verification and replacement semantics | Move ordering and threat geometry |
| 3 | NNUE conditional work and instruction scheduling | Time allocation and clock/increment asymmetry |
| 4 | Repetition, endgames and Syzygy interaction | SMP cooperation, voting and scheduling |

Each investigation was instructed to read the relevant current implementation, trace prior changes and primary test evidence, consider alternatives, and choose one concrete patch with cost/failure/validation analysis. Researchers wrote separate reports and did not edit engine source or submit tests. The lead implements candidates in isolated baseline-rooted worktrees. The orchestrator reviews the reports' mechanisms and coverage; it corrected a TT-bound overstatement and an obsolete PEXT implementation reference before synthesis.

## Prioritized experiments

The ranks are research priorities, not measured Elo. They weigh causal specificity, cost, interaction risk, novelty after bounded prior-art searching, and ability to falsify the proposed mechanism.

| Priority | Investigation | Concrete change | Why it merits testing | Main reason it could lose |
|---|---|---|---|---|
| 1 | [02: correction reliability](02-correction-reliability.md) | Add `(!excludedMove || bestMove)` to the final correction update | A fail-low on alternatives cannot upper-bound the full position; no new state or constants | Existing pessimism may usefully identify fragile positions and other heuristics may have adapted to it |
| 2 | [07: repetition at the qsearch horizon](07-repetition-endgames.md) | Preserve an already detected draw on ordinary qsearch completion/TT return, without writing the raised result | Logging-only runtime diagnostics reproduced a recognized quiet draw followed by a losing qsearch return | Game-level incidence is unmeasured; lost TT writes and changed fail-soft magnitudes may cost strength |
| 3 | [03: child TT bound direction](03-tt-semantics.md) | Allow a parent cutoff when the child numeric disagreement lacks the bound direction needed to establish it | Reuses an already loaded bound, without new probes or storage | Even an inconclusive child bound can warn empirically that the parent entry is stale |
| 4 | [04: queen escape occupancy](04-move-ordering.md) | Remove the queen's origin before verifying an apparent escape from a lesser slider | Corrects a reproducible false move-order bonus using one conditional attack query | Rare useful cases may not repay the added work; some retreats on the ray are tactical sacrifices |
| 5 | [06: final NNUE dependency chain](06-nnue-compute.md) | Use two final-layer dot-product accumulators on VNNI/NEON dot-product targets | Intended exact-output speed improvement, building on distinct earlier-layer optimizations | The final layer is small; merge/register costs or compiler scheduling may erase the gain |
| 6 | [01: selective-search disagreement](01-search-confidence.md) | Reduce quiet LMR slightly when a credible TT bound conflicts with correction direction | Uses disagreement rather than duplicating the already-used correction magnitude | Extra selectivity features are coupled, rarely active, and can fail at longer time controls |
| 7 | [08: unscored SMP worker abstention](08-smp-cooperation.md) | Exclude sentinel scores from vote normalization/aggregation and prefer an eligible scored winner | An unevaluated worker can currently distort all other vote weights | Incidence may be negligible at standard controls; concentrated short-search benefit may not translate to Elo |
| 8 | [05: increment-aware time disadvantage](05-time-management.md) | Compare clocks plus the existing horizon's expected increments | Distinguishes temporary low bank time from sustainable future budget | Weakens a recently accepted saver and can spend future time too eagerly |

### Why candidate 02 was selected first

The excluded-move search asks how good a position's *other* moves are after removing the stored move. Its upper bound is about that restricted set. The final learning code can currently lower structural and continuation correction entries using this upper bound, although those entries represent the unrestricted board position. The mismatch persists even without hash collisions because the excluded move is absent from the learning keys. The no-alternative case can train from an artificial singular-search alpha boundary.

The proposed guard removes only the excluded-search/no-best-move final updates. Positive evidence from a searched alternative remains useful in the full move set and is retained, as is the separate positive multi-cut update. Selective search makes those bounds heuristic, so the argument is directional rather than a formal minimax proof. The report audits the reused stack frame and static-evaluation branch as well as the exact write condition. [Baseline search source](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp).

The strongest counterargument is that an evaluation penalty for “only one good move” can be a useful risk signal even if it is not a literal evaluation residual. Correction history has worked with this behavior since its introduction. Thus it is a credible experiment, not an established bug fix. Candidate 02's first local result, recorded by the lead, is **265 wins / 261 losses / 474 draws**, **+1.39 Elo ±11.80** at 1+0.01 seconds. This interval leaves the sign unresolved. The lead's exact conditions and candidate SHA belong in the [ledger](../EXPERIMENTS.md), which supersedes this snapshot.

### Important distinctions between the next candidates

Candidate 07 is the best next strength-testing target after runtime confirmation of its mechanism. Raising alpha because a drawing move exists does not by itself ensure qsearch returns that draw: outside check, the move picker normally omits quiet moves. A late return floor avoids disturbing in-check evasion pruning. A new floor-derived TT entry is suppressed because repetition depends on the path, although older entries and ancestor graph-history effects remain. The report deliberately preserves actual-draw, maximum-ply and mate exits and documents their exceptions.

The lead authorized a separate logging-only diagnostic worktree after the source dossier was complete. It retained baseline return values and TT writes, and preserved benchmark signature **1648567**. The default bench recorded **3,841** upcoming-repetition detections, of which **103** survived the initial cutoff check; **9 TT returns and 16 ordinary final returns** were below the remembered draw score. Two events were PV final returns and 23 were non-PV events. This is workload-specific incidence, not representative game incidence.

The proposed legal-history seed also reproduced the mechanism through ordinary UCI, without a custom qsearch harness: the PV qsearch child had input window `[-32001,32001]`, recognized draw score `-1`, and returned `-351` from the losing static/capture search. The history was the report's initial FEN followed by six king moves, with `go depth 1 searchmoves f8e8` reaching the intended seventh-move child. This strengthens the causal evidence but supplies no Elo evidence. The [diagnostic report](../results/repetition-diagnostic.md) records commands, hashes, exact instrumentation, logs, and limits; [report 07](07-repetition-endgames.md) contains the return-path audit. Exhaustive edge-case harness testing remains separate work.

For candidate 03, child-bound algebra concerns the value of the stored TT move. A lower bound for its child gives an upper bound on that move's value after negation; it cannot upper-bound every other legal parent move. The proposal refines the existing stored-line consistency heuristic. It should not be advertised as making all TT cutoffs formally sound.

Candidate 04 changes move ordering, not legality or the neural evaluation. Its example is concrete: with a black rook on a8 and white queen on a6, Qa5 remains on the rook's ray, but the pre-move occupancy mask treats it as an escape. The current false bonus is 50,760 ordering points; these are not centipawns. Origin removal detects the continuing attack while preserving a real escape such as Qb6.

Candidate 06 changes instruction scheduling while preserving tested outputs. The lead subsequently completed 20 paired fixed-depth whole-engine timing comparisons on M1 Max, after the engine builds and matches had stopped. The estimated speedup was −1.15%, with approximate 95% interval [−2.35%, +0.06%]. This does not establish a useful speedup. The candidate is set aside and is not being submitted to Fishtest from this evidence. The branch is active only on applicable instruction sets, and x86 speed remains unmeasured. See the [ledger](../EXPERIMENTS.md) for all raw timings and limitations.

Candidate 01 deliberately rejects a generic “large correction means more search” proposal because the baseline already uses correction magnitude in multiple pruning/reduction/extension decisions. It instead proposes bounded protection for quiet moves under directional disagreement. It remains more speculative and coupled than the first three candidates.

Candidate 08 treats a worker that has never produced a score as absent evidence. Its `-VALUE_INFINITE` sentinel can currently become the minimum used to normalize every worker's vote, adding roughly 32,000 points per observed score and overwhelming normal score differences. Two aggregation guards prevent that; a third selection guard repairs the same-move, equal-PV-length case where a no-score main thread could retain invalid metadata despite a scored helper. All-no-score fallback and existing decisive/inexact-loss eligibility remain intact. Synthetic cases support the mechanics, but live incidence should be measured before a large SMP test.

The lead's second fixed 1,000-game screen, for candidate 03, completed at **282 wins / 285 losses / 433 draws**, **−1.04 Elo ±11.21**. Candidate 04's third screen completed at **267 wins / 262 losses / 471 draws**, **+1.74 Elo ±11.70**. All three local screens are inconclusive; their point estimates do not meaningfully rank the candidates.

Candidate 06 preserved benchmark signature **1648567** and passed the lead's 80,000 scalar-reference comparisons. Inspected ARM assembly showed eight serial dot products becoming two four-instruction chains; cross-compiled x86 VNNI assembly showed four becoming two two-instruction chains, without spills. The actual local host is an **Apple M1 Max, 10 cores, 32 GiB**, distinct from the historical M3 Pro examples in report 06. These observations support implementation equivalence and the scheduling mechanism, not a speed or Elo gain. All latest game and timing evidence remains in the [ledger](../EXPERIMENTS.md).

## Repository understanding and coverage

The [architecture report](architecture.md) explains the control flow, selective search, state and hash abstractions, current neural features, hardware sharing, build paths, and validation ecosystem. The frozen baseline has **119 tracked text files, totaling 33,039 lines**: 76 engine/build files, 33 tests/tooling/CI files, and 10 top-level metadata/documentation/license files. These are file/line counts, not a measure of insight or correctness.

The machine-readable [coverage manifest](coverage.json) identifies every baseline file by git blob, line count, type, named reader, and reading status. **All 119 tracked baseline files were read in full across the team; no file remains pending.** Full reading of source/header files is distinguished from full reading of metadata and license text. This is a collective reading claim, not a claim that every agent independently read every file.

The lead read the central search/evaluation/history/TT and board-move/attack implementation. The orchestration agent read the frontend, engine ownership, options, score conversion, state implementation, time management, all neural feature files, memory/shared-memory/NUMA/thread facilities, benchmarks, tuning, build/universal support, tests, CI, scripts, and project metadata. Specialists read complete move-picker, neural-inference, and Syzygy implementations plus the source ranges required by their investigations. Complete file inventories are preserved in their reports and the manifest.

This scope does not claim exhaustive reading of every historical commit, the separate NNUE trainer or Fishtest repositories, downloaded network weights, all training data, generated executables, or every past failed personal experiment. The historical and web searches are bounded, documented prior-art checks. A candidate's absence from those results is not proof of worldwide novelty.

## How to decide whether a candidate improves Elo

Keep each engine candidate based independently on the frozen baseline and preserve exact build, network, signature, opening, seed, and result records. Correctness and deterministic checks come before matches, but passing them does not measure strength. A fixed local screen should finish without optional stopping; it primarily excludes gross failures. The lead's declared local screens use paired openings and retain all results.

For a playing-strength claim, let a standard Fishtest test reach its declared result, then seek independent longer-control confirmation as appropriate. TT/selective-search changes need depth-scaling scrutiny; time-management changes need multiple clock regimes; SMP changes need multithread tests; exact-output speed changes need relevant hardware. The official [test guide](https://official-stockfish.github.io/docs/fishtest-wiki/Creating-my-first-test.html) prescribes atomic ideas and STC-to-LTC progression. The [statistical documentation](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html) explains the sequential procedure and normalized-Elo hypotheses.

Do not sum optimistic Elo estimates from selected candidates or combine failed conceptual patches into a union to seek a lucky pass. Selection among many candidates creates bias; the official [FAQ](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-FAQ.html) discusses this explicitly. Preserve failed variants as evidence, and treat a failed candidate as a useful falsification rather than silently rerolling it.

## Source and review notes

Current implementation claims above are grounded in the frozen repository and the detailed reports' source inventories. Historical test numbers in those reports are attributed to official accepted commit/PR records when direct Fishtest retrieval was unavailable. They are not represented as independently downloaded fresh run results. Primary sources were preferred to secondary chess-programming summaries. The lead's current Fishtest run is separate from all historical precedent.

This orchestration document is a research decision record. The [experiment ledger](../EXPERIMENTS.md) is authoritative for what the lead actually built, tested, published, or submitted and for the latest statistical result.

## Completion record

Eight research reports, the architecture explanation, and the 119-file coverage manifest are complete. Current-source mechanisms were cross-reviewed; the report-only candidate proposals do not themselves modify engine behavior. All local Markdown artifact links were checked, and referenced historical commit objects were verified against the available git history. A separately authorized logging-only diagnostic confirmed candidate 07's behavior without changing baseline search results. Its production patch then passed the paired history/no-history UCI probe, 75 functional tests, 20 reproducibility cases, and an inconclusive 1,000-game screen (+3.13 ±11.93 Elo). There is **no proven Elo gain**. Candidate 02 has an active Fishtest investigation; candidate 07 is submitted as a second independent Fishtest trial; candidate 06 is set aside after failing to demonstrate a speedup. The [ledger](../EXPERIMENTS.md) records the final measurements and current test URLs. A scheduled follow-up continues the experimental work in the lead task.
