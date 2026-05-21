# Loan Default Feature Store — Slideument Outline

**Assignment**: CS611 MLE Assignment 1 · Task 2
**Format**: 8-slide slideument (PDF), self-contained handout for technical + non-technical readers
**Design principle**: Every body slide answers **what I decided** and **why I decided it that way**.
**How to use this file**: Each block below = one slide. Paste the body text into Google Slides / PowerPoint, then add the visual suggested in italics at the bottom of each block. Footer convention shown at the very bottom.

---

## Slide 1 — Title, Context & Scope of This Deck

**Title**: Loan Default Feature Store — Medallion Architecture
**Subtitle**: What tables I built in bronze, silver, and gold — and why I designed them that way.
**Byline**: [Your Name] · CS611 MLE Assignment 1 · 21 May 2026

**Context**
I'm a data scientist at a financial institution that issues cash loans. The eventual goal is a machine-learning model that predicts, **at the point of loan application**, whether a borrower will default. This assignment is the **data foundation** for that model: building production-grade *feature* and *label* stores compliant to the Medallion Architecture, so the next phase — model training — has clean, point-in-time-correct inputs to work with.

**Scope of this deck**
This deck documents the *data layer* only: the bronze, silver, and gold tables I designed, the trade-offs I made at each stage, and the leakage controls baked into the design. Modelling is out of scope (next assignment).

**Status today** (small line at the bottom):
Bronze code written and executed · Silver code written, ready to run · Gold layer designed, implementation next.

*Visual suggestion: a horizontal three-segment ribbon — bronze (filled), silver (outlined), gold (dashed) — sets the reader's expectations before they turn the page. Optionally, put a small "Today / Next" pointer below the ribbon: Today = data pipeline (this deck); Next = model training (next assignment).*

---

## Slide 2 — The Raw Material (and the First Design Decision)

**Four CSVs landed in `/data/`. The very first decision I had to make was which of these is a feature and which is a label.**

| File | Grain | What's in it | My decision |
|---|---|---|---|
| `feature_clickstream.csv` | user × month | 20 numeric web-behaviour features `fe_1` – `fe_20` | Feature source |
| `features_attributes.csv` | user × month | `Name`, `Age`, `SSN`, `Occupation` | Feature source |
| `features_financials.csv` | user × month | `Annual_Income`, `Credit_Mix`, `Outstanding_Debt`, EMI, etc. | Feature source |
| `lms_loan_daily.csv` | loan × day | Daily loan repayment history | **Label-only — never a feature** |

**Why split this way (the reasoning, not the rule)**
Repayment columns in `lms_loan_daily` describe what happened *after* the loan was issued. If they entered the feature store, the model would learn from the answer itself — classic **target leakage**. So I drew a hard line: `lms_loan_daily` is the *only* source for the label store and contributes *zero* columns to the feature store.

*Visual suggestion: the table above with the last row in a contrasting fill colour, and a "TARGET LEAKAGE RISK ⇒ label-only" arrow pointing to it.*

---

## Slide 3 — Why Medallion (and not just one cleaning notebook)

**Decision**: Use a three-layer medallion architecture instead of a single end-to-end cleaning script.

**Three reasons I made that call**
1. **Separation of concerns** — a bug in cleaning logic should never corrupt the raw landing zone. With bronze immutable, I can always rebuild silver and gold from scratch.
2. **Cheap re-runs** — when I change a silver rule, I don't re-download or re-parse raw data; I just re-read bronze. This will matter even more when datasets grow.
3. **Audit trail** — every monthly partition is dated and traceable, so any future model can be tied back to the exact data it was trained on.

**One sentence per layer's job**

| Layer | What it owns | Format | Schema enforced? |
|---|---|---|---|
| **Bronze** | Land raw data, partitioned by `snapshot_date`. No interpretation. | CSV | No |
| **Silver** | Cast types, drop garbage, bound-check outliers. | Parquet | Yes |
| **Gold** | Join into the ML-ready feature/label tables. | Parquet | Yes (business-ready) |

*Visual suggestion: a recoloured bronze→silver→gold flow diagram in your own palette — never paste the Databricks original verbatim, it signals copy-paste.*

---

## Slide 4 — Bronze: What I Built and Why

**Tables produced** (24 monthly partitions per source, Jan 2023 → Dec 2024)
- `datamart/bronze/feature_clickstream/bronze_clickstream_YYYY_MM_DD.csv`
- `datamart/bronze/features_attributes/bronze_attributes_YYYY_MM_DD.csv`
- `datamart/bronze/features_financials/bronze_financials_YYYY_MM_DD.csv`

**Design decisions**

| Decision | Reason |
|---|---|
| Stored as **CSV, not Parquet** | Bronze's job is *fidelity* — disk should mirror what the source system gave us. Compression and typing belong in silver. |
| Partitioned **by month** (one file per `snapshot_date`) | Enables incremental backfill and lets me re-process a single month without touching the rest. |
| **One dispatch function** `process_bronze_table(date, src, dir, name, spark)` instead of one file per source | Adding a fourth source is a one-line change to the `datasets` list, not a new module — keeps modularity without code duplication. |
| **Only `snapshot_date` is parsed** (from `dd/MM/yyyy` → `DateType`) | Bronze never interprets data values; we only touch the partition key so the filter is reliable. |

*Visual suggestion: a small folder-tree diagram showing `datamart/bronze/feature_clickstream/bronze_clickstream_2023_01_01.csv` — concrete output anchors the reader.*

---

## Slide 5 — Silver: Where the Real Cleaning Decisions Live

**Tables produced** (one Parquet directory per source per month)
`datamart/silver/<dataset>/silver_<dataset>_YYYY_MM_DD.parquet/`

**Why Parquet here, but not in bronze?**
Silver is the first layer downstream code is *allowed* to depend on. Parquet enforces a typed, columnar, compressed schema on disk — so any consumer (PySpark, pandas, a future warehouse) reads the same shape every time.

**Per-source decisions — each row = "what EDA showed → what I did → why"**

| Source | What EDA showed | What I did | Why this rule |
|---|---|---|---|
| **Clickstream** | All 20 features already numeric, low null rate. | Cast `fe_1`–`fe_20` → Integer, `Customer_ID` → String, `snapshot_date` → Date. | Type discipline only — no row drops needed when the data is already clean. |
| **Attributes** | `SSN` contained sentinel garbage `"#F%$D@*&8"`; `Occupation` had `"_______"` placeholders; `Age` mixed letters & numbers; outliers below 18 and above 70. | Drop sentinel rows; regex-strip Age to digits; clamp `18 ≤ Age ≤ 70`. | Sentinel rows are unrecoverable. The 18–70 band is the realistic borrowing population; everything outside is almost certainly data-entry error or out-of-target. |
| **Financials** | European decimal commas, stray underscores in numerics; some columns had impossibly large values (e.g. `Outstanding_Debt` in the millions vs. realistic max ~$4,500 per EDA percentiles). Sentinel garbage in `Credit_Mix = "_"`, `Payment_Behaviour = "!@9#%8"`. | Strip underscores; swap `,` → `.` for decimals; bound-check every numeric column; drop sentinel rows. | Bounds chosen from EDA percentile inspection — not arbitrary. Filtering at silver means gold and the model never see polluted distributions. |

**Anchor**: Every threshold on this slide came from reading the corresponding EDA notebook, not from guessing.

*Visual suggestion: three short column cards side-by-side — Clickstream, Attributes, Financials — with the most striking "saw → did" pair for each in large type.*

---

## Slide 6 — Gold: ML-Ready Design + Leakage Controls

**Two tables, two purposes**

**A. Gold feature store** — `datamart/gold/feature_store/gold_feature_store_YYYY_MM_DD.parquet`
Built by left-joining silver `clickstream` ⨝ `attributes` ⨝ `financials` on `(Customer_ID, snapshot_date)`.

**B. Gold label store** — `datamart/gold/label_store/gold_label_store_YYYY_MM_DD.parquet`
Built by filtering `lms_loan_daily` to `mob = 6` (six months on book), then: `dpd ≥ 30 ⇒ label = 1`, else `0`. Keep `loan_id, Customer_ID, label, label_def, snapshot_date`.

**Design decisions**

| Decision | Reason |
|---|---|
| **Left join** silver tables, not inner join | An inner join silently shrinks the population whenever one source is missing a customer. A left join preserves coverage and lets the model handle missingness explicitly. |
| **Drop `Name` and raw `SSN`** | No predictive value, PII risk, and per-customer identifiers can let a model overfit to individuals. |
| **`mob = 6` and `dpd ≥ 30`** as the default-flag definition | Standard early-default window in lending. Matches the Lab 2 label definition so the label store stays consistent across assignments. |

**Leakage controls (built into this design, not bolted on later)**
- No column from `lms_loan_daily` ever enters the feature store.
- The label is defined *strictly forward in time* (mob = 6) relative to the feature snapshot — no temporal leakage.
- Train/test split happens *after* gold is loaded, never before — no train-test contamination.

**Status**: design finalised; implementation is the next step. Bronze and silver are shaped to make the gold join trivial.

*Visual suggestion: a small join diagram — three silver tables flowing into the gold feature store, and `lms_loan_daily` flowing separately into the gold label store, with join keys labelled.*

---

## Slide 7 — How It Runs

**Stack**
PySpark (`local[*]`) · Docker + docker-compose · JupyterLab.

**Orchestration loop** (`main.py`, abbreviated)
```python
dates    = generate_first_of_month_dates("2023-01-01", "2024-12-01")
datasets = [("clickstream", ...), ("attributes", ...), ("financials", ...)]

for d in dates:
    for name, src, bronze_dir, _ in datasets:
        process_bronze_table(d, src, bronze_dir, name, spark)
for d in dates:
    for name, _, bronze_dir, silver_dir in datasets:
        process_silver_table(d, name, bronze_dir, silver_dir, spark)
# gold loop to follow
```

**Two-command reproducibility**
```
docker-compose up         # build + start container + JupyterLab
python main.py            # rebuild the entire datamart from raw CSVs
```

**Why this shape?** A nested loop over `(month × dataset)` means adding a new source or extending the backfill window is a config change, not a code change.

*Visual suggestion: a left-to-right flow strip — `raw CSVs → bronze loop → silver loop → (gold loop) → datamart/` — with the gold step greyed out to mirror the honest status from Slide 1.*

---

## Slide 8 — Status, Next Steps, How to Run

**Honest status**

| Layer | Code | Output on disk |
|---|---|---|
| Bronze | ✅ Written | ✅ 24 monthly partitions × 3 sources |
| Silver | ✅ Written | 🟡 Empty — needs a clean end-to-end run |
| Gold | ⏳ Designed (see Slide 6) | ⏳ Not yet built |

**What I'd do next (in priority order)**
1. Implement `process_gold_feature_store` and `process_gold_label_store`; wire into `main.py`. Run end-to-end.
2. Smoke-test the pipeline by fitting a tiny logistic regression on gold — pass/fail check that the feature store is ML-compatible.
3. Add a small data-quality summary per silver partition (rows in, rows filtered, % dropped) so silent data loss is visible.
4. Unit tests on each transformation function with a fixture row per source.

**How to run this pipeline yourself**
```
git clone <repo-url>
cd MLE_ASM1
docker-compose up
# then inside the container:
python main.py
```
Output appears in `datamart/{bronze,silver,gold}/`.

**Contact**: [Your Name] · [email] · GitHub: [link]

*Visual suggestion: the status table above with traffic-light colours (green/amber/grey) — instantly readable at a glance.*

---

## Footer Convention (apply to every slide)

- **Left**: `Loan Default Feature Store · MLE Assignment 1`
- **Right**: `Slide N / 8`
- **Font**: same family as body, ~10pt, light grey

## Style Guide (apply once across the deck)

- **Palette**: navy `#0A2540` primary, single accent (e.g. amber `#F2A900`), neutral greys for body, white background.
- **Font**: one sans-serif throughout (Inter, Calibri, or Arial). Avoid mixing fonts.
- **Density rule**: every slide is self-explanatory as a handout, but no slide exceeds ~80 words of body text outside tables.
- **Diagrams over screenshots** wherever possible — and recolour any borrowed diagrams into your own palette so they feel native.
- **Export as PDF** for submission.
