#!/usr/bin/env python3
"""
Agent 02 — Content Validator
Scores, filters, clusters, and ranks scraped content.
Reads from .tmp/scraped_content_latest.json
Output saved to .tmp/validated_content_latest.json
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

# ── Config ────────────────────────────────────────────────────
INPUT_FILE  = Path(".tmp/scraped_content_latest.json")
OUTPUT_DIR  = Path(".tmp")

MIN_VIEWS   = int(os.getenv("MIN_VIEWS_FILTER", "10000"))
MIN_ER      = float(os.getenv("MIN_ER_FILTER", "2.0"))
VIRAL_VIEWS = int(os.getenv("VIRAL_VIEWS_THRESHOLD", "100000"))
VIRAL_ER    = float(os.getenv("VIRAL_ER_THRESHOLD", "5.0"))
MAX_AGE_DAYS = 30

# Scoring weights (must sum to 1.0)
W_VIEWS    = 0.40
W_ER       = 0.35
W_COMMENTS = 0.25

N_CLUSTERS = 6  # topic clusters


# ── Scoring ───────────────────────────────────────────────────
def score_post(row: pd.Series) -> float:
    """Return a 0–100 composite score."""
    v = min(row["views"] / VIRAL_VIEWS, 1.0) * 100
    e = min(row["engagement_rate"] / VIRAL_ER, 1.0) * 100
    c = min(row["comments"] / 10_000, 1.0) * 100
    return round(W_VIEWS * v + W_ER * e + W_COMMENTS * c, 2)


# ── Topic Clustering ──────────────────────────────────────────
TOPIC_LABELS = [
    "Claude Code Tutorials",
    "AI Automation Income",
    "Agent Setup Walkthroughs",
    "AI vs Traditional Tools",
    "N8N / No-Code Automation",
    "Vibe Coding & AI Dev",
]

def cluster_topics(df: pd.DataFrame) -> pd.DataFrame:
    texts = (df["hook_text"].fillna("") + " " + df["full_caption"].fillna("")).tolist()
    if len(texts) < N_CLUSTERS:
        df["topic_cluster"] = "General AI Content"
        return df
    try:
        vec   = TfidfVectorizer(max_features=200, stop_words="english")
        X     = vec.fit_transform(texts)
        km    = KMeans(n_clusters=min(N_CLUSTERS, len(texts)), random_state=42, n_init=10)
        labels = km.fit_predict(X)
        cluster_map = {i: TOPIC_LABELS[i % len(TOPIC_LABELS)] for i in range(N_CLUSTERS)}
        df["topic_cluster"] = [cluster_map[l] for l in labels]
    except Exception as e:
        print(f"  ⚠️  Clustering failed: {e}")
        df["topic_cluster"] = "General AI Content"
    return df


# ── Trend Detection ───────────────────────────────────────────
def detect_trends(df: pd.DataFrame) -> dict:
    """Flag topics/formats appearing repeatedly in top results."""
    top = df.head(20)
    topic_counts  = Counter(top["topic_cluster"].tolist())
    format_counts = Counter(top["format"].tolist())

    repeat_viral_topics  = [t for t, c in topic_counts.items()  if c >= 3]
    sustained_formats    = [f for f, c in format_counts.items() if c >= 3]

    return {
        "repeat_viral_topics": repeat_viral_topics,
        "sustained_formats":   sustained_formats,
        "top_topic_counts":    dict(topic_counts.most_common(6)),
        "top_format_counts":   dict(format_counts.most_common(5)),
    }


# ── Recommendation ────────────────────────────────────────────
def make_recommendation(ranked_topics: pd.DataFrame, trends: dict) -> str:
    if ranked_topics.empty:
        return "Not enough data for a recommendation."
    top = ranked_topics.iloc[0]
    avg_views = int(top["avg_views"])
    topic     = top["topic_cluster"]
    reason    = "highest average views this week"
    if topic in trends["repeat_viral_topics"]:
        reason += " + repeat viral signal (3+ top posts)"
    return f'**Recommended topic: "{topic}" — avg {avg_views:,} views, {reason}**'


# ── Main ──────────────────────────────────────────────────────
def run(input_path: str | None = None) -> str | None:
    src = Path(input_path) if input_path else INPUT_FILE
    if not src.exists():
        print(f"❌  Input not found: {src}\n   Run content_scraper.py first.")
        return None

    print("\n🚀  Agent 02 — Content Validator\n" + "─"*50)

    df = pd.read_json(src)
    print(f"📥  Loaded {len(df)} posts from scraper")

    # ── Filter ────────────────────────────────────────────────
    cutoff   = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    df["post_date_dt"] = pd.to_datetime(df["post_date"], errors="coerce")
    before   = len(df)
    df = df[
        (df["views"] >= MIN_VIEWS) &
        (df["engagement_rate"] >= MIN_ER) &
        (df["post_date_dt"] >= cutoff)
    ].copy()
    print(f"🔍  Filtered: {before} → {len(df)} posts (removed {before - len(df)} low performers)")

    if df.empty:
        print("❌  No posts passed the filter. Lower MIN_VIEWS or MIN_ER in .env.")
        return None

    # ── Score ─────────────────────────────────────────────────
    df["score"] = df.apply(score_post, axis=1)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    # ── Cluster ───────────────────────────────────────────────
    df = cluster_topics(df)

    # ── Trend detection ───────────────────────────────────────
    trends = detect_trends(df)

    # ── Ranked topic summary ──────────────────────────────────
    topic_stats = (
        df.groupby("topic_cluster")
        .agg(
            avg_views=("views", "mean"),
            avg_er=("engagement_rate", "mean"),
            post_count=("views", "count"),
        )
        .reset_index()
        .sort_values("avg_views", ascending=False)
        .round(2)
    )
    topic_stats["avg_views"] = topic_stats["avg_views"].astype(int)
    topic_stats["trend_flag"] = topic_stats["topic_cluster"].apply(
        lambda t: "🔁 REPEAT VIRAL" if t in trends["repeat_viral_topics"] else ""
    )

    recommendation = make_recommendation(topic_stats, trends)

    # ── Top formats ───────────────────────────────────────────
    format_stats = (
        df.groupby("format")
        .agg(avg_shares=("likes", "mean"), post_count=("views", "count"))
        .reset_index()
        .sort_values("avg_shares", ascending=False)
        .head(3)
    )

    # ── Save outputs ──────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest = OUTPUT_DIR / "validated_content_latest.json"
    output = {
        "generated_at": datetime.now().isoformat(),
        "recommendation": recommendation,
        "top_topics": topic_stats.to_dict(orient="records"),
        "top_formats": format_stats.to_dict(orient="records"),
        "trends": trends,
        "validated_posts": df.drop(columns=["post_date_dt"]).to_dict(orient="records"),
    }
    with open(latest, "w") as f:
        json.dump(output, f, indent=2)
    with open(OUTPUT_DIR / f"validated_content_{ts}.json", "w") as f:
        json.dump(output, f, indent=2)

    # ── Print report ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"📊  VALIDATION REPORT")
    print(f"{'='*70}")
    print(f"\n{recommendation}\n")
    print("🏆  TOP 5 TOPICS BY AVERAGE VIEWS")
    print(tabulate(topic_stats.head(5), headers="keys", tablefmt="rounded_outline", showindex=False))
    print("\n📹  TOP 3 FORMATS BY SHARES")
    print(tabulate(format_stats, headers="keys", tablefmt="rounded_outline", showindex=False))
    if trends["repeat_viral_topics"]:
        print(f"\n🔁  REPEAT VIRAL SIGNAL: {', '.join(trends['repeat_viral_topics'])}")
    if trends["sustained_formats"]:
        print(f"📈  SUSTAINED FORMATS:    {', '.join(trends['sustained_formats'])}")
    print(f"\n💾  Saved → {latest}\n")

    return str(latest)


if __name__ == "__main__":
    run()
