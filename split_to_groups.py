#!/usr/bin/env python3
"""
split_to_groups.py

Splits interactions.csv into one CSV per petri dish (group of bees).

Two bees belong to the same group if they have ever interacted.
Transitivity is handled via union-find, so if A↔B and B↔C, all three
are in the same group even if A and C never met directly.

Output files are named:  group_<bee1>_<bee2>_..._<beeN>.csv
and written to the same directory as the input file (or --output-dir).

Usage:
    python split_to_groups.py --input interactions.csv
    python split_to_groups.py --input interactions.csv --output-dir results/
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


# ── Union-Find ─────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self):
        self._parent = {}

    def find(self, x):
        if x not in self._parent:
            self._parent[x] = x
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])  # path compression
        return self._parent[x]

    def union(self, x, y):
        self._parent[self.find(x)] = self.find(y)

    def groups(self):
        """Return a dict mapping root → set of members."""
        result = defaultdict(set)
        for x in self._parent:
            result[self.find(x)].add(x)
        return dict(result)


# ── Helpers ────────────────────────────────────────────────────────────────────

def group_filename(bee_ids: list) -> str:
    """Stable filename from a sorted list of bee IDs."""
    clean = [b.replace("ArUcoTag#", "") for b in sorted(bee_ids)]
    return "group_" + "_".join(clean) + ".csv"


# ── Main ────────────────────────────────────────────────────────────────────────

def split(input_path: str, output_dir: str = None) -> None:
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input not found: {src}")

    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Read all rows ──────────────────────────────────────────────────────────
    with open(src, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not rows:
        print("No interactions found — nothing to split.")
        return

    # ── Build groups via union-find ────────────────────────────────────────────
    uf = UnionFind()
    for row in rows:
        b1, b2 = row["bee1_id"], row["bee2_id"]
        uf.union(b1, b2)

    # root → sorted list of bee IDs in this group
    root_to_bees = {root: sorted(members) for root, members in uf.groups().items()}

    # bee → root  (for fast row assignment)
    bee_to_root = {bee: root for root, bees in root_to_bees.items() for bee in bees}

    # root → rows belonging to this group
    root_to_rows = defaultdict(list)
    for row in rows:
        root = bee_to_root[row["bee1_id"]]
        root_to_rows[root].append(row)

    # ── Write one CSV per group ────────────────────────────────────────────────
    print(f"\nFound {len(root_to_bees)} group(s):\n")
    for root, bees in sorted(root_to_bees.items(), key=lambda kv: kv[1]):
        group_rows = root_to_rows[root]
        fname = group_filename(bees)
        out_path = out_dir / fname

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(group_rows)

        print(f"  {fname}")
        print(f"    Bees        : {', '.join(bees)}")
        print(f"    Interactions: {len(group_rows)}")

    print(f"\nOutput directory: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Split interactions CSV by bee group")
    parser.add_argument("--input",      required=True, help="Path to interactions.csv")
    parser.add_argument("--output-dir", default=None,  help="Directory for output CSVs")
    args = parser.parse_args()

    split(args.input, args.output_dir)


if __name__ == "__main__":
    main()