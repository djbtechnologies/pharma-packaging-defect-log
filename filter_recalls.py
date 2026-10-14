"""
Filter the raw recalls down to packaging and labeling problems.

Steps:
1. Load the saved API data from data/raw/.
2. Keep recalls whose reason_for_recall contains a packaging keyword as a
   whole word ("cap" matches, "capsule" doesn't). A few phrases that use those
   words but aren't about packaging, like "within expiry", are ignored.
3. Drop duplicate recall numbers and flag injectable products.
4. Keep the log at 500 rows or fewer so every row can be reviewed by hand:
   injectables only, then the most recent full years that fit.

Output: data/packaging_recalls.csv

Usage: python filter_recalls.py
       python filter_recalls.py --review   (prints random kept/dropped reasons to spot-check the filter)
"""

import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
OUT_PATH = Path("data/packaging_recalls.csv")
MAX_ROWS = 500

# Packaging keywords as regex patterns. "s?" allows a plural, "\.?" an optional period.
KEYWORDS = [
    # labels and printed info
    r"labels?", r"labeling", r"labeled", r"labell(?:ed|ing)",
    r"mislabel(?:ed|ing)", r"mislabell(?:ed|ing)", r"mis-label(?:ed|led|ing)?",
    r"inserts?", r"outserts?", r"lot numbers?", r"expiration", r"expiry", r"exp\.? dates?",
    r"mix-up", r"mixup", r"mix up", r"mixed up",
    # packaging components
    r"packaging", r"packages?", r"packaged", r"blisters?", r"cartons?", r"containers?",
    r"closures?", r"caps?", r"seals?", r"sealed", r"stoppers?", r"crimp(?:s|ed)?",
    r"vials?", r"syringes?", r"ampou?les?", r"pouch(?:es)?", r"overwrap", r"foil",
    r"desiccants?", r"droppers?", r"tamper",
    # integrity failures
    r"leak(?:s|ed|ing|age)?", r"crack(?:s|ed)?",
    # packaging line errors
    r"foreign (?:tablets?|capsules?)", r"out of sequence", r"short fill", r"under-?fill(?:ed)?",
]
KEYWORD_RE = re.compile(r"\b(" + "|".join(KEYWORDS) + r")\b", re.IGNORECASE)

# Phrases that contain a keyword but describe something else (sterility,
# stability, or potency). These get blanked out before keyword matching.
IGNORE_PHRASES = [
    r"within (?:the )?(?:expiry|expiration)",          # "all products within expiry"
    r"supports? (?:the )?(?:printed |assigned |labeled )?(?:expiry|expiration)",
    r"(?:at|through|before|prior to) (?:the )?(?:labeled )?(?:expiry|expiration)",
    r"expiry stability point", r"shelf life expiry", r"calibration expiry",
    r"retest or expiration date in firm's container/closure system",
    r"label(?:ed|led|ing)? (?:claims?|claimed|concentration|potency|amount|strength)",
    r"(?:less|more|lower|higher) than (?:the )?label(?:ed|led)?",
]
IGNORE_RE = re.compile("|".join(IGNORE_PHRASES), re.IGNORECASE)

# openfda.route never says "INJECTION" in this data, it lists the actual route.
INJECTABLE_ROUTES = {
    "INJECTION", "INTRAVENOUS", "INTRAMUSCULAR", "SUBCUTANEOUS", "INTRADERMAL",
    "INTRAVITREAL", "INTRATHECAL", "EPIDURAL", "INTRA-ARTICULAR", "INTRA-ARTERIAL",
    "INTRAVASCULAR", "INTRACAVERNOUS", "INTRALESIONAL", "INTRASYNOVIAL",
    "INTRAPERITONEAL", "PARENTERAL", "INFILTRATION", "PERINEURAL", "INTRACAUDAL",
    "SUBARACHNOID", "RETROBULBAR", "INTRAOCULAR", "INTRAMEDULLARY", "SOFT TISSUE",
    "INTRAPLEURAL", "INTRACARDIAC",
}
INJECTABLE_WORDS = re.compile(r"\b(injection|injectable|vials?|syringes?)\b", re.IGNORECASE)


def load_raw():
    records = []
    for path in sorted(RAW_DIR.glob("enforcement_*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records += json.load(f)["results"]
    return records


def find_keywords(reason):
    cleaned = IGNORE_RE.sub(" ", reason)
    return sorted({m.group(0).lower() for m in KEYWORD_RE.finditer(cleaned)})


def is_injectable(rec):
    routes = [r.upper() for r in rec.get("openfda", {}).get("route", [])]
    if any(r in INJECTABLE_ROUTES for r in routes):
        return "Yes"
    if INJECTABLE_WORDS.search(rec.get("product_description", "")):
        return "Yes"
    return "No"


def to_table(records):
    rows = []
    for rec in records:
        reason = rec.get("reason_for_recall", "")
        rows.append({
            "recall_number": rec.get("recall_number"),
            "event_id": rec.get("event_id"),
            "report_date": pd.to_datetime(rec.get("report_date"), format="%Y%m%d"),
            "recalling_firm": rec.get("recalling_firm"),
            "product_description": rec.get("product_description", ""),
            "route": ", ".join(rec.get("openfda", {}).get("route", [])),
            "injectable": is_injectable(rec),
            "classification": rec.get("classification"),
            "status": rec.get("status"),
            "reason_for_recall": reason,
            "keywords": ", ".join(find_keywords(reason)),
        })
    df = pd.DataFrame(rows)
    df["year"] = df["report_date"].dt.year
    return df


def limit_rows(df):
    print(f"{len(df)} recalls matched a packaging keyword")
    if len(df) > MAX_ROWS:
        df = df[df["injectable"] == "Yes"]
        print(f"{len(df)} are injectables")
    if len(df) > MAX_ROWS:
        # Add full years from newest to oldest until the next year would go over.
        keep, total = [], 0
        for year, n in df["year"].value_counts().sort_index(ascending=False).items():
            if total + n > MAX_ROWS:
                break
            keep.append(year)
            total += n
        df = df[df["year"].isin(keep)]
        print(f"kept {min(keep)} to {max(keep)}: {len(df)} recalls")
    return df


def review(df, n=25, seed=42):
    kept = df[df["keywords"] != ""].sample(n, random_state=seed)
    dropped = df[df["keywords"] == ""].sample(n, random_state=seed)
    print(f"--- {n} random kept ---")
    for _, r in kept.iterrows():
        print(f"[{r['keywords']}] {r['reason_for_recall'][:200]}")
    print(f"\n--- {n} random dropped ---")
    for _, r in dropped.iterrows():
        print(f"- {r['reason_for_recall'][:200]}")


def main():
    df = to_table(load_raw())
    print(f"{len(df)} recalls loaded")
    if "--review" in sys.argv:
        review(df)
        return

    df = df[df["keywords"] != ""].drop_duplicates(subset="recall_number")
    df = limit_rows(df)
    df = df.sort_values(["report_date", "recall_number"], ascending=[False, True])
    df.to_csv(OUT_PATH, index=False)
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()
