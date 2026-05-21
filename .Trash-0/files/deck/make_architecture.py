"""Render the medallion architecture diagram as a PNG."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

CREAM = "#F1EFED"
TEAL = "#54BBC6"
SAGE = "#BFD192"
LAV = "#EEDEEE"
PERI = "#BACDE5"
DARK = "#1A2A3A"
TXT = "#2A2A2A"

# Bronze / Silver / Gold tinted versions
BRONZE = "#D9B382"
SILVER = "#C8CFD6"
GOLD = "#E8C977"


def box(ax, x, y, w, h, label, sublabels, facecolor, edgecolor=DARK):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.2,
            edgecolor=edgecolor,
            facecolor=facecolor,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.32,
        label,
        ha="center",
        va="top",
        fontsize=14,
        fontweight="bold",
        color=DARK,
    )
    for i, sub in enumerate(sublabels):
        ax.text(
            x + w / 2,
            y + h - 0.7 - i * 0.32,
            sub,
            ha="center",
            va="top",
            fontsize=8.5,
            color=TXT,
        )


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=18,
            linewidth=1.6,
            color=DARK,
        )
    )


fig, ax = plt.subplots(figsize=(13, 5.5), facecolor=CREAM)
ax.set_facecolor(CREAM)
ax.set_xlim(0, 13)
ax.set_ylim(0, 5.5)
ax.axis("off")

# Layer band labels at top
for x, label, color in [
    (0.3, "Raw", "#BFC4C9"),
    (2.9, "Bronze", BRONZE),
    (5.7, "Silver", SILVER),
    (8.6, "Gold", GOLD),
    (11.5, "ML", PERI),
]:
    ax.add_patch(
        FancyBboxPatch(
            (x, 4.7),
            1.3,
            0.5,
            boxstyle="round,pad=0.01,rounding_size=0.1",
            facecolor=color,
            edgecolor="none",
        )
    )
    ax.text(x + 0.65, 4.95, label, ha="center", va="center", fontsize=12, fontweight="bold", color=DARK)

# Raw column (4 CSVs)
raw_files = [
    "feature_clickstream.csv",
    "feature_attributes.csv",
    "feature_financials.csv",
    "lms_loan_daily.csv",
]
for i, name in enumerate(raw_files):
    y = 3.6 - i * 0.85
    ax.add_patch(
        FancyBboxPatch(
            (0.05, y),
            1.85,
            0.65,
            boxstyle="round,pad=0.01,rounding_size=0.08",
            facecolor="white",
            edgecolor=DARK,
            linewidth=0.8,
        )
    )
    ax.text(0.975, y + 0.32, name, ha="center", va="center", fontsize=8, color=TXT)

# Bronze layer (4 boxes, one per source)
bronze_names = ["bronze/clickstream", "bronze/attributes", "bronze/financials", "bronze/lms"]
for i, name in enumerate(bronze_names):
    y = 3.6 - i * 0.85
    box(
        ax,
        2.5,
        y,
        2.1,
        0.65,
        name,
        ["CSV · partitioned by month"],
        BRONZE,
    )
    arrow(ax, 1.95, y + 0.32, 2.48, y + 0.32)

# Silver layer (4 cleaned)
silver_names = [
    ("silver/clickstream", "type-cast · drop nulls"),
    ("silver/attributes", "drop SSN · clean text"),
    ("silver/financials", "Tukey outliers · types"),
    ("silver/lms", "compute mob & dpd"),
]
for i, (name, sub) in enumerate(silver_names):
    y = 3.6 - i * 0.85
    box(ax, 5.2, y, 2.3, 0.65, name, [sub + "  · Parquet"], SILVER)
    arrow(ax, 4.63, y + 0.32, 5.18, y + 0.32)

# Gold layer (3 tables)
gold_boxes = [
    (
        "gold/feature_store_clickstream",
        ["20 behavioural features"],
        3.5,
    ),
    (
        "gold/feature_store_customer",
        ["attributes JOIN financials", "one-hot, engineered"],
        2.2,
    ),
    (
        "gold/label_store",
        ["mob = 6 · dpd ≥ 30 → 1"],
        0.6,
    ),
]
for name, sub, y in gold_boxes:
    box(ax, 8.1, y, 2.7, 0.95 if len(sub) > 1 else 0.7, name, sub, GOLD)

# Arrows from silver to gold (selected ones)
arrow(ax, 7.53, 3.92, 8.08, 3.95)        # clickstream silver -> gold clickstream
arrow(ax, 7.53, 3.07, 8.08, 2.65)        # attributes -> customer
arrow(ax, 7.53, 2.22, 8.08, 2.65)        # financials -> customer
arrow(ax, 7.53, 1.37, 8.08, 0.95)        # lms -> label

# ML node
ax.add_patch(
    FancyBboxPatch(
        (11.0, 1.8),
        1.85,
        1.5,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        facecolor=PERI,
        edgecolor=DARK,
        linewidth=1.2,
    )
)
ax.text(11.925, 2.85, "Default-risk", ha="center", va="center", fontsize=11, fontweight="bold", color=DARK)
ax.text(11.925, 2.55, "classifier", ha="center", va="center", fontsize=11, fontweight="bold", color=DARK)
ax.text(11.925, 2.20, "(next assignment)", ha="center", va="center", fontsize=8.5, color=TXT, style="italic")

# Arrows from gold to ML
arrow(ax, 10.82, 3.95, 11.0, 3.0)
arrow(ax, 10.82, 2.65, 11.0, 2.7)
arrow(ax, 10.82, 0.95, 11.0, 2.4)

# Footer caption
ax.text(
    6.5,
    0.05,
    "Raw drop-zone → immutable Bronze partitions → cleaned Silver tables → ML-ready Gold feature & label stores",
    ha="center",
    va="bottom",
    fontsize=9,
    color=TXT,
    style="italic",
)

plt.tight_layout()
out = r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\architecture.png"
plt.savefig(out, dpi=200, facecolor=CREAM, bbox_inches="tight")
print("saved", out)
