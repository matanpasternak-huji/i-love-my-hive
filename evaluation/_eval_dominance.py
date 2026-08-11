import csv, re
from collections import defaultdict

def tag(s):
    m = re.search(r"(\d+)", s)
    return m.group(1) if m else s.strip()

COUPLES = [frozenset({"5", "7"}), frozenset({"3", "9"})]

def tally(rows):
    # rows: list of (pair:frozenset, winner:str)  winner may be 'canceled'
    wins = {c: defaultdict(int) for c in COUPLES}
    decided = {c: 0 for c in COUPLES}
    for pair, win in rows:
        if pair not in wins:
            continue
        if win == "canceled":
            continue
        wins[pair][win] += 1
        decided[pair] += 1
    return wins, decided

def report(name, rows):
    wins, decided = tally(rows)
    print(f"\n=== {name} ===")
    for c in COUPLES:
        members = sorted(c)
        tot = decided[c]
        print(f"  couple {{{','.join(members)}}}: {tot} decided interactions")
        dom = None
        for b in members:
            w = wins[c][b]
            pct = w / tot * 100 if tot else 0
            print(f"    bee {b}: {w} wins ({pct:.1f}%)")
            if tot and w / tot > 0.5:
                dom = b
        print(f"    -> dominant: {'bee ' + dom if dom else 'none (no >50% majority)'}")

# manual (all annotations, first hour = full manual set)
manual = []
with open("evaluation/interactions_visualized_long_video_manual_annotations_1h.csv") as f:
    for r in csv.DictReader(f):
        manual.append((frozenset({r["winner"].strip(), r["loser"].strip()}), r["winner"].strip()))

# model positives (ALL detected interactions, full video)
model_all = []
model_1h = []
for r in csv.DictReader(open("evaluation/interactions.csv")):
    pair = frozenset({tag(r["bee1_id"]), tag(r["bee2_id"])})
    win = "canceled" if r["winner"].strip() == "canceled" else tag(r["winner"])
    model_all.append((pair, win))
    if int(r["entrance_frame"]) <= 60 * 60 * 30:
        model_1h.append((pair, win))

report("MANUAL (ground truth, 1 h)", manual)
report("MODEL positives (full video)", model_all)
report("MODEL positives (first hour only)", model_1h)