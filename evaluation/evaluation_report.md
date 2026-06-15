# Interaction Detection Evaluation

Comparison of detector output (`interactions.csv`) against manual ground-truth
annotations (`interactions_visualized_long_video_manual_annotations_1h.csv`).

## Method

- **Frame rate:** 30 fps. All times converted to frames.
- **Annotation window:** the manual annotations cover only the **first hour**
  (≤ 108000 frames). The detector output runs to ~128 min, so detected rows with
  `entrance_frame > 108000` are excluded — otherwise every later detection would
  be wrongly counted as a false positive.
- **Match criterion:** a manual and a detected interaction match when they involve
  the **same pair of bees** and both endpoints are within **±2 s (60 frames)**:
  `|Δentrance| ≤ 60` **and** `|Δexit| ≤ 60` (so duration agrees within ±4 s).
- **Matching:** one-to-one, greedy by smallest combined endpoint error.

| Outcome | Definition |
|---|---|
| **True Positive (TP)**  | In both files within tolerance |
| **False Negative (FN)** | In manual, not matched by detector |
| **False Positive (FP)** | In detector (≤ 1 h), not in manual |

## Results

| Metric | Value |
|---|---|
| Manual interactions (ground truth) | 47 |
| Detected interactions (≤ 1 h)      | 70 |
| **True Positives**  | **24** |
| **False Negatives** | **23** |
| **False Positives** | **46** |

| Score | Formula | Value |
|---|---|---|
| **Precision** | TP / (TP + FP) = 24 / 70 | **0.343 (34.3 %)** |
| **Recall**    | TP / (TP + FN) = 24 / 47 | **0.511 (51.1 %)** |
| **F1**        | 2·P·R / (P + R)          | **0.410 (41.0 %)** |

## Outcome (dominant-bee) accuracy

Measured only over the 24 true positives — did the detector pick the same winner
as the manual annotation?

| Metric | Value |
|---|---|
| Correct outcome | 22 / 24 |
| **Accuracy** | **91.7 %** |

The 2 mismatches:

| Pair | Time (manual) | Manual winner | Detected winner |
|---|---|---|---|
| {3,9} | 8:04–8:10  | 3 | 9 |
| {3,9} | 8:28–8:36  | 3 | 9 |

## Notes / observations

- **Recall is hurt by fragmentation.** Several long manual interactions are split
  into many short detections that fail the strict endpoint tolerance — e.g. manual
  `{5,7} 6:44–9:22` (≈2.5 min) has no single detection covering it. Long ground-truth
  events (`6:44–9:22`, `14:45–15:18`, `20:03–20:52`, `22:30–23:36`) are all missed.
- **Precision is hurt by over-segmentation / extra events**, predominantly on the
  `{3,9}` pair, where the detector reports many short interactions with no manual
  counterpart.
- **`canceled` detections** (max-duration cutoffs) count as wrong outcome if matched;
  here they fell into FP and did not affect outcome accuracy.
- Metrics are sensitive to the ±60-frame tolerance. A looser window (e.g. allowing
  overlap rather than matched endpoints) would raise recall, since many FN/FP pairs
  overlap in time but differ at the boundaries.

## Overall dominance per couple

A separate, higher-level question: regardless of per-interaction matching, does the
model reach the **same dominance conclusion** as the manual observer for each couple?

**Dominant bee** = the bee that won **more than 50 %** of that couple's decided
interactions (interactions ending in `canceled` have no winner and are excluded).
The manual figure uses all manual annotations (first hour); the model figure uses
all of the model's positive detections across the full video.

### Couple {5, 7}

| Source | Decided | Bee 5 wins | Bee 7 wins | Dominant |
|---|---|---|---|---|
| Manual (1 h)       | 24 | 13 (54.2 %) | 11 (45.8 %) | **Bee 5** |
| Model (1 h)        | 23 | 18 (78.3 %) |  5 (21.7 %) | **Bee 5** |
| Model (full video) | 28 | 20 (71.4 %) |  8 (28.6 %) | **Bee 5** |

### Couple {3, 9}

| Source | Decided | Bee 3 wins | Bee 9 wins | Dominant |
|---|---|---|---|---|
| Manual (1 h)       |  23 |  5 (21.7 %) | 18 (78.3 %) | **Bee 9** |
| Model (1 h)        |  45 |  9 (20.0 %) | 36 (80.0 %) | **Bee 9** |
| Model (full video) | 103 | 32 (31.1 %) | 71 (68.9 %) | **Bee 9** |

### Verdict

✅ **The model's dominance estimation is correct for both couples** — it identifies
**bee 5** as dominant over bee 7, and **bee 9** as dominant over bee 3, matching the
manual observation.

Note that for {5, 7} the manual margin is fairly thin (54.2 % vs 45.8 %, a 2-interaction
lead); the model agrees on direction but with a wider margin (71.4 %). For {3, 9} both
sources show a clear, consistent majority for bee 9. So even
though per-interaction precision/recall are modest, the **aggregate behavioral
conclusion (who dominates whom) is recovered correctly.**