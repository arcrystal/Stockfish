# Stockfish Elo research

Personal fork: [arcrystal/Stockfish](https://github.com/arcrystal/Stockfish). Studied baseline: [`031dfeb4`](https://github.com/arcrystal/Stockfish/commit/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3). Research and reproducible evidence are maintained on `codex/elo-research`; each engine experiment has its own branch directly from that baseline.

**No Elo improvement is established yet.** The correction-history and repetition-floor candidates both completed standard Fishtest STC with a rejected gainer hypothesis: −2.07 Elo over 32,416 games and −0.34 Elo over 86,496 games, respectively. Neither advances to LTC. Their source mechanisms and functional checks remain useful findings, but did not establish a strength gain.

The child TT bound and queen escape trials also completed with rejected STC gainer hypotheses: −1.18 Elo over 47,680 games and −0.96 Elo over 54,048 games. Their intervals include zero; neither establishes a gain or advances to LTC. All four game-tested candidates are now set aside. The completed second research pass prioritized measured decision value per unit of search and found no supported production candidate. The old speculative ranking is superseded by the [second-pass synthesis](agents/second-pass-synthesis.md). The [experiment ledger](EXPERIMENTS.md) records exact conditions and preserved API evidence.

## Second-pass evidence

The new orchestration team examined LMR verification feedback, reuse of singular-search alternatives, pawn-history residuals, cost-aware ordering, and redundant exchange calculations. Two behavior-preserving instruments and an extended LMR observer matched the unchanged baseline on all 64 fixed UHO positions. The singular-alternative idea was rejected before game testing; LMR reliability and extra pawn-history terms lacked evidence to change search policy. See the [synthesis](agents/second-pass-synthesis.md) for the reasoning and negative findings.

The one candidate built for a speed experiment is **qsearch SEE result reuse**: when an earlier exchange test already proves a later threshold test, retain that answer locally. Its baseline bench is unchanged, all 75 functional and 20 reproducibility checks pass, and a broader SEE harness passes 17,795,196 threshold queries over 2,172 legal moves in 70 positions, including promotion, en passant, castling, pins and king recapture fixtures. The completed 20-pair timing test found only +0.10% search speedup, with a 95% interval [−0.18%, +0.38%]. It is set aside without Fishtest. The completed causal audit used 64 fresh roots and 128 preselected, state-checked single-event depth interventions. Both pawn-history groups had 0/64 recovered threshold decisions; 107/128 interventions left local node counts unchanged. This sparse result provides no basis for a pawn-history reduction coefficient; it does not establish that all such policies are ineffective. The [ledger](EXPERIMENTS.md) records exact conditions and evidence.

## What was researched

An orchestration agent directed eight investigations, using two specialist agents in four waves under the four-agent concurrency limit. The team read all **119 tracked files / 33,039 lines** at the pinned baseline. The [coverage manifest](agents/coverage.json) identifies each file by git blob and named reader; its inventory and hashes were checked against git. This covers the engine repository, including tests and build support. It does not claim exhaustive reading of all historical revisions, external training data, or binary network weights.

Start with the [architecture and purpose report](agents/architecture.md) and the [orchestration decision record](agents/orchestration.md). The detailed studies document current behavior, bounded prior-art searches, primary sources, proposed mechanisms, contrary evidence, costs, and validation plans:

| Study | Hypothesis |
|---|---|
| [01 — selective search](agents/01-search-confidence.md) | Protect quiet moves when credible TT evidence conflicts with correction direction |
| [02 — correction learning](agents/02-correction-reliability.md) | Avoid training the full position from an excluded-search fail-low |
| [03 — TT semantics](agents/03-tt-semantics.md) | Respect child bound direction in the existing parent-cutoff consistency check |
| [04 — move ordering](agents/04-move-ordering.md) | Remove false queen escape bonuses caused by origin-square occupancy |
| [05 — time management](agents/05-time-management.md) | Include expected increments when judging relative clock disadvantage |
| [06 — NNUE computation](agents/06-nnue-compute.md) | Split the final dot product into independent instruction chains |
| [07 — repetition and endgames](agents/07-repetition-endgames.md) | Preserve an available quiet draw through ordinary quiescence completion |
| [08 — SMP cooperation](agents/08-smp-cooperation.md) | Prevent workers with no evaluated score from changing voting normalization |

The ranking reflects mechanisms and testing cost, not measured Elo. Related historical successes are attributed to their original commits and test conditions. No claim of universal novelty is made.

## Implemented experiments

| Branch on personal fork | Commit | Bench | Status |
|---|---|---:|---|
| [codex/correction-bound](https://github.com/arcrystal/Stockfish/tree/codex/correction-bound) | `685e5a03` | 1283493 | Local 1,000 games: +1.39 ±11.80 Elo, inconclusive; Fishtest STC rejected |
| [codex/tt-bound](https://github.com/arcrystal/Stockfish/tree/codex/tt-bound) | `144dff77` | 1485122 | Local 1,000 games: −1.04 ±11.21 Elo, inconclusive; Fishtest STC rejected |
| [codex/queen-escape](https://github.com/arcrystal/Stockfish/tree/codex/queen-escape) | `442230b9` | 1281886 | Local 1,000 games: +1.74 ±11.70 Elo, inconclusive; Fishtest STC rejected |
| [codex/nnue-chains](https://github.com/arcrystal/Stockfish/tree/codex/nnue-chains) | `4d8dd713` | 1648567 | Exact outputs; speedup −1.15%, interval [−2.35%, +0.06%]; set aside |
| [codex/repetition-floor](https://github.com/arcrystal/Stockfish/tree/codex/repetition-floor) | `948232b7` | 1586754 | Local 1,000 games: +3.13 ±11.93 Elo, inconclusive; Fishtest STC rejected |
| [codex/qsearch-see-reuse](https://github.com/arcrystal/Stockfish/tree/codex/qsearch-see-reuse) | `5e16e3f3` | 1648567 | Exact outputs; speedup +0.10%, interval [−0.18%, +0.38%]; set aside |

Each of these six candidates passes the existing 75 functional tests and 20 reproducibility cases. The baseline also passes the signature and all 20 normal/Chess960 perft cases. Numerical and functional checks establish different things from game strength. None of the candidate changes has been combined with another.

## Reproduction and evidence

The local host is an Apple M1 Max with 10 cores and 32 GiB memory. Engine builds use Apple clang 21.0.0, profile-guided compilation, `ARCH=apple-silicon`, and the same embedded network. The [ledger](EXPERIMENTS.md) records the full source, binary, network, runner, and opening-book identifiers. Worktrees, downloaded networks, and executables live in the locally ignored `.research-tools/` directory and are not part of the research commit.

`run_match.py` runs predeclared paired-opening comparisons and preserves commands, hashes, seeds, timestamps, Fastchess logs, and PGNs. The four game screens each use exactly 1,000 games at 1+0.01 with different predetermined seeds. They screen for gross failures; they cannot resolve a small gain. Timing uses `compare_speed.py`, which checks identical work and alternates baseline/candidate order over 20 pairs. `check_affine.cpp` compares the final neural layer with a scalar reference; `inspect_affine.cpp` produces inspectable architecture-specific assembly. `repetition_probe.py` replays the same root board with and without the relevant history through ordinary UCI commands.

All collected evidence is under [results](results/). A current public Fishtest snapshot is retained alongside the live run link. Standard SPRT tests should reach their declared result without optional stopping. A passing STC candidate needs independent longer-control confirmation before making a broad strength claim. The [official test guide](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test) and [Fishtest mathematics](https://github.com/official-stockfish/fishtest/wiki/Fishtest-Mathematics) explain the procedure and interpretation.

## Continuing the experiment

The implemented candidates and completed second-pass screens are exhausted without a supported winner. No Fishtest test is active, and no candidate is eligible for LTC. The app reports that the previously recorded **Continue Stockfish Elo testing** follow-up no longer exists; no replacement was created. Speculative leads, including the unexecuted cost-ordering diagnostic, remain documented; they are not validated upgrades. A resumed research effort should state a new diagnostic before testing another policy, preserve the pinned baseline and keep experiments separate.
