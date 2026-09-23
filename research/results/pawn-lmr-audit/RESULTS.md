# Completed matched-root pawn-history audit

Completed 23 September 2026 at 03:08:45 UTC. **The audit found no verification-supported recovery in either group. It does not justify a pawn-history LMR coefficient or a new Fishtest submission.** It also does not prove that every possible pawn-history allocation rule is ineffective.

## Frozen experiment and validity

The [frozen protocol](protocol-frozen.md) and [frozen runner](runner-frozen.py) were copied only after their SHA-256 hashes matched the discovery manifest. The sample contains 64 seed-20260921 UHO roots, excluding every exact FEN from the previous 64-root corpus. Each process used Threads=1, Hash=16 and `go depth 13`.

All 64 discovery searches matched the unchanged baseline at every recorded iteration score, PV, node count and best move. Default bench remained **1648567**. The discovery corpus produced **324,410 eligible observed scouts**, of which **319,252** completed as finite, non-decisive fail-lows. Each root had at least one common matching bucket for positive and nonpositive parent pawn-history entries.

The selection manifest was frozen before treatment: SHA-256 **`5932cf589f772e3562b5bbe7a2c898e7b143becccf04e41c4ce3dd091392195a`**. The prescribed SHA-256 ordering selected one event per sign within one shared depth/scout-depth/move-rank/cut-node bucket per root, for **128 targets**. No target was replaced or selected using a deeper result.

All **128/128 replays were valid**. The same instrumented binary replayed the entire untouched root prefix; the selected ordinal, rolling prefix digest and all 44 entry fields matched before its single scout-depth increment. The runtime guard would abort on mismatch. Post-run checks independently required the full identity, exactly one perturbation, original `d` unchanged in the recorded anchor, and effective treatment depth `d+1`. Ordinary subsequent verification and learning remained active. There were no aborted, invalid or retargeted trials.

Diagnostic binary SHA-256: `f6b301ee1b2a5f62c8d9162d5dd75f55a2dc43cd03db4ac1385d4fdf14749840`. Unmodified baseline binary SHA-256: `3bc6989c07a680e8478a997b5fcafb877724ac4909509341d1b0d373e7eb6083`. The [corpus manifest](corpus.json) records exact roots, line indices, artifact hashes and timestamps. [Selection](selection.json), [summary](summary.json), and [analysis source](analyze.py) retain the pairing and calculations; raw engine outputs and individual discovery/treatment records retain all observations.

## Outcomes

| Treatment group | Selected roots | Still fail-low | Exposed illusion | Verification-supported recovery | Accepted without further verification |
|---|---:|---:|---:|---:|---:|
| Positive parent pawn history | 64 | 64 | 0 | 0 | 0 |
| Nonpositive parent pawn history | 64 | 64 | 0 | 0 | 0 |

The paired recovery table has **0 positive-only, 0 nonpositive-only, 0 both, and 64 neither**. There are no discordant roots, so a conditional sign/McNemar comparison contains no information about which sign targets recoveries better. We do not report a zero-width Wald or bootstrap interval. As a descriptive binomial model only, the exact 95% interval for each 0/64 recovery rate is **[0%, 5.60%]**. Root selection, the specific matching restrictions and possible correlations among openings limit generalization; these are not universal engine-error bounds.

The original and deeper scout scores differed in 14 positive-history cases and 11 controls, but every score remained at or below that event's unchanged alpha. Thus the depth intervention was not merely absent from the implementation: it changed some answers without recovering an initially discarded move.

## Search costs and downstream effects

| Measure | Positive history | Nonpositive history |
|---|---:|---:|
| Total immediate scout/move node delta | +135 | +23 |
| Mean immediate node delta per target | +2.11 | +0.36 |
| Median immediate node delta | 0 | 0 |
| Immediate delta range | −2 to +51 | 0 to +6 |
| Cases with unchanged immediate node count | 52/64 | 55/64 |
| Total full-root node delta | +35,007 | −55,782 |
| Median full-root node delta | 0 | 0 |
| Full-root delta range | −8,798 to +34,296 | −35,928 to +13,312 |
| Entire root iteration trace unchanged | 47/64 | 54/64 |
| Actual root best move changed | 6/64 | 2/64 |

Each group's baseline roots collectively searched **1,862,859 nodes**. Scout and immediate-move deltas are identical here because no treated scout became a fail-high requiring ordinary verification. The code consistently raised the requested scout depth and adjusted `ss->reduction`; a nominal ply increase does not guarantee extra expanded nodes. Existing TT cutoffs and child hindsight logic can make that request operationally redundant. The diagnostic did not attribute individual zero-work cases to a specific cause, so those mechanisms remain explanations to investigate, not measured classifications.

Unchanged immediate node counts can still accompany different scores, depth-dependent history updates or TT state, so they do not prove the whole computation was inert. Conversely, the large spread in downstream root cost and eight changed best moves does not establish an improvement. Whole-root adaptation, history updates, transpositions and node-dependent tie/draw behavior can magnify one local change. No deeper truth reference or match result was obtained for those root choices.

## Decision

The proposed causal story was that positive pawn-context history would preferentially identify quiet moves whose reduced fail-lows hide verification-supported improvements. This fixed audit observed **no such recoveries**, and therefore provides no measured sign enrichment from which to justify a production rule. The high number of observed eligible events does not compensate for the small number of independently treated root pairs or the many operationally redundant depth requests.

Retain this as a completed negative/insufficient mechanism experiment. Do not fit a coefficient to the zero-recovery sample, widen the matching bins after seeing the results, or promote changed root moves as strength gains. No production engine change, speed claim, Elo claim or Fishtest submission follows from this audit.

## Lossless publication and reproduction

Large raw `.log` and `.json` files are published as `.gz` files. The [compression manifest](compression-manifest.json) records original and compressed lengths and SHA-256 hashes. `research/archive_evidence.py` verified every decompressed hash before replacing an original file; no trial or field was removed. The readable corpus, selection and summary remain uncompressed.

To restore the frozen runners' expected filenames, run `gzip -dk research/results/pawn-lmr-audit/*.gz` from the repository root, then check restored hashes against the manifest. The retained `analyze.py` intentionally refuses to overwrite `summary.json`; compare a newly generated summary in a separate copy. Discovery and replay also create outputs exclusively, so reproduce in a fresh output directory, preserving the original evidence. Rebuild the diagnostic from pinned baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3` with `instrumentation.patch`, the recorded NNUE and the corpus's engine settings; the frozen runner records the exact binary identities used for this audit.
