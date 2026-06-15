import csv, re

FPS = 30
WINDOW = 60          # +-2 s on entrance and exit
CUTOFF = 60 * 60 * FPS  # manual annotations cover first hour only (108000)

def tag(s):
    m = re.search(r"(\d+)", s)
    return m.group(1) if m else s.strip()

# ---- manual (ground truth) ----
manual = []
with open("evaluation/interactions_visualized_long_video_manual_annotations_1h.csv") as f:
    for r in csv.DictReader(f):
        manual.append({
            "winner": r["winner"].strip(),
            "loser":  r["loser"].strip(),
            "pair":   frozenset({r["winner"].strip(), r["loser"].strip()}),
            "ent":    int(r["entrance_frame"]),
            "ext":    int(r["exit_frame"]),
        })

# ---- detected ----
detected = []
with open("evaluation/interactions.csv") as f:
    for r in csv.DictReader(f):
        ent = int(r["entrance_frame"])
        if ent > CUTOFF:
            continue
        b1, b2 = tag(r["bee1_id"]), tag(r["bee2_id"])
        win = "canceled" if r["winner"].strip() == "canceled" else tag(r["winner"])
        detected.append({
            "pair": frozenset({b1, b2}),
            "ent":  ent,
            "ext":  int(r["exit_frame"]),
            "winner": win,
        })

# ---- greedy matching: same pair, entrance & exit both within +-WINDOW ----
used = [False] * len(detected)
tp, outcome_correct = [], 0
matched_manual = set()

for mi, m in enumerate(manual):
    best, best_cost = None, None
    for di, d in enumerate(detected):
        if used[di] or d["pair"] != m["pair"]:
            continue
        de, dx = abs(d["ent"] - m["ent"]), abs(d["ext"] - m["ext"])
        if de <= WINDOW and dx <= WINDOW:
            cost = de + dx
            if best_cost is None or cost < best_cost:
                best, best_cost = di, cost
    if best is not None:
        used[best] = True
        matched_manual.add(mi)
        d = detected[best]
        correct = (d["winner"] == m["winner"])
        if correct:
            outcome_correct += 1
        tp.append((m, d, correct))

TP = len(tp)
FN = len(manual) - TP
FP = sum(1 for u in used if not u)

print(f"manual total      : {len(manual)}")
print(f"detected (<=1h)   : {len(detected)}")
print(f"TP                : {TP}")
print(f"FN                : {FN}")
print(f"FP                : {FP}")
precision = TP / (TP + FP) if (TP + FP) else 0
recall    = TP / (TP + FN) if (TP + FN) else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
print(f"precision         : {precision:.3f}")
print(f"recall            : {recall:.3f}")
print(f"f1                : {f1:.3f}")
print(f"outcome correct   : {outcome_correct}/{TP} = {outcome_correct/TP if TP else 0:.3f}")

def fr(f):
    s = f / FPS
    return f"{int(s//60)}:{int(s%60):02d}"

print("\n-- TP detail (manual -> detected, outcome) --")
for m, d, c in tp:
    print(f"  {{{','.join(sorted(m['pair']))}}} man {fr(m['ent'])}-{fr(m['ext'])} win {m['winner']} | "
          f"det {fr(d['ent'])}-{fr(d['ext'])} win {d['winner']} | {'OK' if c else 'WRONG'}")

print("\n-- FN (missed by detector) --")
for mi, m in enumerate(manual):
    if mi not in matched_manual:
        print(f"  {{{','.join(sorted(m['pair']))}}} {fr(m['ent'])}-{fr(m['ext'])} win {m['winner']}")

print("\n-- FP (detected, no manual match) --")
for di, d in enumerate(detected):
    if not used[di]:
        print(f"  {{{','.join(sorted(d['pair']))}}} {fr(d['ent'])}-{fr(d['ext'])} win {d['winner']}")
