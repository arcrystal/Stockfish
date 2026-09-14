# Occupancy-aware queen escape ordering

## Recommendation

Test a narrow correction to the quiet-move threat term: when a queen appears to escape a lesser piece's attack, remove its origin square before confirming that its destination is safe from opposing bishops and rooks. A queen retreating down the same attack ray currently receives a large escape bonus because its original square blocks the pre-move attack mask.

This is a geometrically identifiable scoring error with a small implementation and no new parameter. It does not establish an Elo gain. The additional attack lookup could cost more than improved ordering saves, and some nominally unsafe retreats are tactically justified.

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. No engine source/build/branch/commit/remote content was changed by this investigation.

## Exact patch

In `src/movepick.cpp`, within `MovePicker::score<QUIETS>()`, immediately after the existing threat delta:

```diff
             int v = 20 * (bool(threatByLesser[pt] & from) - bool(threatByLesser[pt] & to));
+            if (pt == QUEEN && v > 0)
+            {
+                const auto [bishopAttacks, rookAttacks] =
+                  Attacks::both_attacks_bb(to, pos.pieces() ^ from);
+                if ((bishopAttacks & pos.pieces(~us, BISHOP))
+                    || (rookAttacks & pos.pieces(~us, ROOK)))
+                    v = 0;
+            }
             value += PieceValue[pt] * v;
```

`Attacks::` is required: `movepick.cpp` does not import that namespace. The helper is already available through `position.h`/`attacks.h`. A comment such as “The queen's origin can hide an attack on its destination” would explain the condition. Preserve every current scoring coefficient and stage threshold in the first test.

## Existing move ordering

`MovePicker` selects a pseudo-legal TT move first, then SEE-qualified captures, good quiets, bad captures, and bad quiets. Evasions and quiescence use separate stage sequences. Quiet sorting uses butterfly history, pawn history, five continuation histories, safe direct-check bonuses, lesser-piece threats, and low-ply history. The good/bad quiet threshold is `-14000`; only sufficiently high-scoring quiets are sorted at shallow depths. [1, 2]

For each quiet batch, the threat masks are built once from the current position. Knights and bishops consider pawn attacks; rooks consider pawn, knight, and bishop attacks; queens also consider rook attacks. Pawns and kings get zero from this term. `Position::attacks_by<Pt>()` uses `pieces()` as occupancy, so an opposing slider's ray stops on the moving queen's original square. [1, 3]

The score contribution is currently:

```cpp
20 * PieceValue[pt] * (attackedBefore(from) - attackedBefore(to))
```

For queens this is `+50,760`, `0`, or `-50,760` ordering points because `QueenValue = 2538`. These are move-order scores, not centipawns or search evaluation units. A false escape bonus can therefore substantially outrank ordinary histories. [1, 4]

## Reproducible geometric example

Use the legal position:

```text
r5k1/8/Q7/8/8/8/8/6K1 w - - 0 1
```

Black has a rook on a8, White a queen on a6. The rook's pre-move attack ray reaches a6 but stops there. Consequently the current term gives `Qa5` an escape bonus, although after `Qa5` the same rook attacks a5. `Qb6` really leaves the ray and should retain its bonus. A bishop analogue places a black bishop on f8 and white queen on d6: `Qc5` stays on the bishop's ray, while `Qd5` leaves it.

An independent Python ray-walk calculation, without building or running the engine, checked these four cases:

| Attacker | Queen move | Existing threat contribution | With post-move destination occupancy |
|---|---|---:|---:|
| Ra8 | a6a5 | +50,760 | 0 |
| Ra8 | a6b6 | +50,760 | +50,760 |
| Bf8 | d6c5 | +50,760 | 0 |
| Bf8 | d6d5 | +50,760 | +50,760 |

This validates the geometric mechanism only. It does not demonstrate a wrong engine best move, a tactical-suite improvement, or an Elo gain.

## Why a queen-only conditional is sufficient for this blind spot

Removing a quiet move's origin can extend an enemy slider ray onto its destination only when the origin lies on that same ray. Among the piece relationships used by this heuristic, this is possible for a queen moving along an opposing bishop's diagonal or rook's rank/file.

A rook cannot retreat along a bishop diagonal, and the lesser attacks used for knights and bishops come only from pawns. Pawn and knight attacks do not depend on occupancy. Thus recalculating every piece's threats would pay for work unrelated to this specific error.

The `v > 0` gate further restricts work to apparently successful escapes: the origin is already threatened and the destination is not present in the old mask. A newly opened attack through the origin necessarily attacked the origin first, so this gate covers the missed destination attacks. If the destination was already marked threatened, current symmetric scoring yields zero and needs no correction.

The origin-only occupancy change is enough for attacks *onto* the destination: whether the destination itself is marked occupied does not change the ray reaching that square. Other blockers remain in place. Quiet queen moves are normal moves, so castling, en passant, and promotions are outside this branch.

The patch intentionally returns the threat delta to zero rather than assigning a new penalty. The existing symmetric policy gives zero whenever both the old and new squares are threatened. This preserves that policy while fixing the occupancy used to classify the new square.

## Search consequences

This alters quiet ordering, not legal move generation or evaluation. Nevertheless, Stockfish is selective: position in the move list affects late-move reductions and pruning. In `src/search.cpp`, the move count is incremented after legality but before the later SEE test. The late-move quiet-skip threshold and reductions can therefore be affected even if a falsely promoted queen retreat is eventually rejected by SEE. A wasted early slot can push a real escape later in the list. [5]

The intended gain is fewer early examinations of queen moves that remain on an unchanged lesser-slider attack, allowing genuine escapes and useful alternatives to receive more search. The countervailing risk is that moving backward on a ray can be a good sacrifice, establish a pin, or exploit a counterthreat. Existing `threatByLesser` is pseudo-attack based and does not fully solve exchanges, pins, or tactics; this patch does not attempt to solve them either.

## Threat increments and alternative ideas

SFNNv16 has incremental threat features, but these are not a ready-made complete attack map. `Dirties::dirtyThreats` stores changed relationships for the previous move; `AccumulatorStack::latest()` exposes the current state's incremental record. The features are intentionally selective: kings emit no direct threats, pawn threat targets exclude several piece types, and pawn-pawn relationships now use separate pair features. Reusing this delta as a full lesser-piece mask would be incorrect without additional accumulated state. [4, 6, 7]

Full hypothetical threat deltas for every unsearched quiet move would require making/updating moves or reproducing substantial update logic before ordering. That is much more expensive than the conditional reverse attack query proposed here.

The following alternatives were examined but not selected:

| Idea | Reason not selected first |
|---|---|
| Threat-conditioned butterfly history | Promising general context separation, but multiplies history state or changes indexing and learning; many interacting call sites |
| Score discovered checks using `gives_check()` | Clear omission in the direct-check bonus, but extra work on all quiets and a familiar broad candidate; safe-check semantics need careful treatment |
| Add checking capture bonus | A previous checking capture bonus was removed with non-regression support in November 2025 |
| Reclassify quiet queen promotions | Generation and `capture_stage()` intentionally agree that all queen promotions belong in the capture stage; changing one side creates duplication/classification problems |
| Score underpromotions as their promoted piece | Pawn-indexed histories, move encoding, and capture-stage conventions require a wider audit; rare events make benefit hard to establish |
| Remove all own queens from batch attack occupancy | Can expose rays through a different stationary queen, especially in promoted positions; the per-move origin-only query is exact for this mechanism |

## Prior work and novelty limits

The escape/unsafe-destination heuristic is longstanding. The July 2023 en-prise penalty implementation explicitly extended an earlier escape bonus and passed both STC and LTC gain tests. The April 2025 simplification consolidated the threat classes and passed non-regression tests. [8, 9]

The November 2025 simplification replaced separate bonuses with `PieceValue` scaling; its LTC non-regression test ran 240,552 games. The February 2026 simplification made source/destination scoring symmetric, passing a 99,852-game LTC non-regression test. These results support preserving the current weights and symmetry in the first experiment. They do not test the proposed origin-removal check. [10, 11]

Repository history searches over `threatByLesser` and related terms, together with GitHub issue/PR searches for threat/queen/occupancy/escape/ray/xray, found no accepted matching fix. This does not establish novelty: failed Fishtest branches, unindexed discussions, or other engines may already contain the same idea.

## Cost, failure modes, and test plan

The patch adds a cheap type/sign condition to quiet scoring and one paired bishop/rook attack query only for apparent queen escapes. On the baseline's ordinary magic-bitboard path this uses multiplication-based attack indexing; on the dual-hyperbola path the helper computes both attacks together. The baseline helper has no PEXT branch. Two color/piece intersections then decide whether to suppress the bonus. It adds no table, history dimension, move buffer, NNUE feature, or UCI option. The occurrence rate and net speed cost must be measured. [12]

Run the candidate independently of correction-history candidate 02. First compile against the frozen baseline, record bench signatures and speed, and exercise a rook-ray and bishop-ray example plus genuine escapes. A temporary diagnostic scorer can verify only the intended queen move contributions differ; do not submit diagnostic logging.

Use paired openings for a local gross-regression screen, then an isolated Fishtest STC test followed by LTC if warranted. Measure wall-clock speed rather than comparing depth alone, because different move ordering changes node counts. If the geometry is correct but Elo regresses, treat this heuristic as too costly or behaviorally over-specialized; do not claim that correcting a move-order score automatically improves strength.

Confidence: high in the occupancy mismatch; high in the proposed narrow geometry; unknown incidence during representative games; unknown net speed and Elo effect.

## Sources

1. Stockfish developers. [Baseline movepick.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/movepick.cpp). Complete local file inspected.
2. Stockfish developers. [Baseline movepick.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/movepick.h). Complete local file inspected.
3. Stockfish developers. [Baseline position.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/position.h), `attacks_by`, `capture`, and `capture_stage`.
4. Stockfish developers. [Baseline types.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/types.h), piece values and dirty records.
5. Stockfish developers. [Baseline search.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), main move loop and history interfaces.
6. Stockfish developers. [Baseline full_threats.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/features/full_threats.h), selective feature mapping. Complete local header inspected.
7. Stockfish developers. [Baseline nnue_accumulator.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/nnue_accumulator.h), incremental-state interfaces. Local header inspected.
8. rn5f107s2 / Stockfish. [Malus during move ordering for putting pieces en prise](https://github.com/official-stockfish/Stockfish/commit/65ece7d985291cc787d6c804a33f1dd82b75736d), July 29, 2023. [LTC record](https://tests.stockfishchess.org/tests/live_elo/64c2004ddc56e1650abba8b3), figures read from the local accepted commit.
9. Carlos Esparza / Stockfish. [Simplify move ordering bonuses for putting piece en prise and escaping capture](https://github.com/official-stockfish/Stockfish/commit/f0de8dc0349bac56021a900910f14a00a729dbc6), April 27, 2025. Accepted diff and test summary inspected locally.
10. Daniel Monroe / Stockfish. [Simplify threat term in movepick, PR 6401](https://github.com/official-stockfish/Stockfish/pull/6401), November 2025. [LTC record](https://tests.stockfishchess.org/tests/view/69063956ea4b268f1fac1f66). PR via GitHub API and accepted commit `9e38023a` inspected.
11. mstembera / Stockfish. [Simplify threat by lesser, PR 6637](https://github.com/official-stockfish/Stockfish/pull/6637), February 2026. [LTC record](https://tests.stockfishchess.org/tests/view/699f4bee2be03365d5073c71). PR via GitHub API and accepted commit `bc28ff15` inspected.
12. Stockfish developers. [Baseline attacks.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/attacks.h), paired slider attack helper and occupancy semantics.
13. Daniel Monroe / Stockfish. [Remove check term in capture movepick](https://github.com/official-stockfish/Stockfish/commit/8551f86efce1d55c3cf5bb639247212a3c290bdf), November 13, 2025. Accepted local diff and recorded non-regression tests.
14. Stockfish developers. [Update NNUE architecture to SFNNv16](https://github.com/official-stockfish/Stockfish/commit/f4bcd404), July 2026. Commit message inspected; confirms pawn-pair features replace pawn-pawn threat interactions. This architectural history is context, not evidence for the move-order candidate.

## Files explicitly read

Complete: `src/movepick.cpp`, `src/movepick.h`, `src/movegen.h`, `src/nnue/features/full_threats.h`, `src/nnue/nnue_accumulator.h`.

Relevant ranges: `src/movegen.cpp:80–175,210–290`; `src/position.h:286–311,348–379`; `src/position.cpp:466–480,641–658,760–808,1145–1290,1386–1438`; `src/search.cpp:638–685,1125–1247,1320–1430,1970–2060`; `src/types.h` piece values, `DirtyThreat`, `DirtyThreats`, and `Dirties`; `src/attacks.h:263–338`; `src/bitboard.h:1–100`; `src/nnue/nnue_accumulator.cpp` reset/push/latest and dirty-record references.

Historical diffs/messages: `f0de8dc0`, `65ece7d9`, `d27298d7`, `20bc1955`, `9e38023a`, `bc28ff15`, `8551f86e`, `f4bcd404`. Source files and references also reuse the earlier correction-history study's confirmed baseline context.
