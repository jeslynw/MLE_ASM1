# MLE Assignment 1 — Context & Guide

## What This Assignment Is

Build a **Medallion Architecture** data pipeline for a feature store, following the same pattern as Lab 2 but applied to 3 new feature datasets.

---

## Medallion Architecture (3 Layers)

```
Raw CSV  →  Bronze  →  Silver  →  Gold
             (copy)    (clean)   (ready for ML)
```

| Layer | Job | Format |
|-------|-----|--------|
| **Bronze** | Slice raw source data by `snapshot_date`, save as partition | CSV |
| **Silver** | Enforce types, clean dirty data, add derived columns | Parquet |
| **Gold** | Business-ready ML table (join, select, aggregate) | Parquet |

---

## Lab 2 Reference (the template)

Lab 2 uses only `lms_loan_daily.csv` to build a **label store**.

### Flow in `main.py`
Loops every month (Jan 2023 → Dec 2024) and calls each layer:
```
for each month:
    bronze_table(date)  → datamart/bronze/lms/bronze_loan_daily_2023_01_01.csv
    silver_table(date)  → datamart/silver/loan_daily/silver_loan_daily_2023_01_01.parquet
    gold_table(date)    → datamart/gold/label_store/gold_label_store_2023_01_01.parquet
```

### Bronze (`utils/data_processing_bronze_table.py`)
- Reads full CSV, filters to one `snapshot_date`, saves as CSV partition
- No transformation — pure slicing

### Silver (`utils/data_processing_silver_table.py`)
1. Cast all columns to correct types (String, Float, Date, Integer)
2. Add `mob` = `installment_num` (Month on Book — which payment number)
3. Add `dpd` (Days Past Due) — derived from `overdue_amt / due_amt` to count missed installments and days late

### Gold (`utils/data_processing_gold_table.py`)
Label definition: filter to `mob == 6`, then:
- `dpd >= 30` → `label = 1` (defaulted)
- else → `label = 0`
- Keep only: `loan_id, Customer_ID, label, label_def, snapshot_date`

---

## Assignment 1 Task

Same 3-layer pattern, but for **feature store** using 3 new datasets:

| File | Contents | Key columns |
|------|----------|-------------|
| `data/feature_clickstream.csv` | 20 numeric web behaviour features per user/month | `fe_1`–`fe_20`, `Customer_ID`, `snapshot_date` |
| `data/features_attributes.csv` | User demographics | `Customer_ID`, `Name`, `Age`, `SSN`, `Occupation`, `snapshot_date` |
| `data/features_financials.csv` | Financial health data | `Customer_ID`, `Annual_Income`, `Num_Bank_Accounts`, `Credit_Mix`, `Outstanding_Debt`, etc., `snapshot_date` |

Note: CSV delimiter is `;` (semicolon), not comma.

### Target folder structure
```
datamart/
├── bronze/
│   ├── clickstream/bronze_clickstream_2023_01_01.csv
│   ├── attributes/bronze_attributes_2023_01_01.csv
│   └── financials/bronze_financials_2023_01_01.csv
├── silver/
│   ├── clickstream/silver_clickstream_2023_01_01.parquet
│   ├── attributes/silver_attributes_2023_01_01.parquet
│   └── financials/silver_financials_2023_01_01.parquet
└── gold/
    ├── feature_store/gold_feature_store_2023_01_01.parquet
    └── label_store/gold_label_store_2023_01_01.parquet   ← reuse from Lab 2
```

---

## Data Leakage Warning

- The label is defined at `mob=6` (6 months after loan start)
- Features must come from **at/before loan application time** — not the future
- The 3 feature files (clickstream, attributes, financials) are user-level snapshots — safe to use
- **Do NOT** use columns from `lms_loan_daily.csv` as features (they contain repayment data = the answer itself)

---

## Known Bug in Starter `main.py`

Line 24: `sparks.sparkContext.setLogLevel("ERROR")` — `sparks` should be `spark`.

---

## Lab 2 vs Assignment 1

| | Lab 2 | Assignment 1 |
|--|-------|-------------|
| Input | `lms_loan_daily.csv` | 3 feature CSVs |
| Gold output | Label store (0/1 labels) | Feature store (ML input features) |
| Key derived cols | `mob`, `dpd` | Type casts, cleaned features, joined table |
| Purpose | Who defaulted? | What did those customers look like? |
