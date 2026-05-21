from pyspark.sql import functions as F
from pyspark.sql.functions import col
from pyspark.sql.types import IntegerType, StringType


def process_feature_store_clickstream_table(snapshot_date_str, silver_clickstream_directory, gold_directory, spark):
    suffix = snapshot_date_str.replace('-', '_')

    filepath = silver_clickstream_directory + f"silver_clickstream_{suffix}.parquet"
    df = spark.read.parquet(filepath)
    print('loaded from:', filepath, 'row count:', df.count())

    out_path = gold_directory + f"gold_feature_store_clickstream_{suffix}.parquet"
    df.write.mode("overwrite").parquet(out_path)
    print("saved to:", out_path)

    return df


def process_feature_store_customer_table(snapshot_date_str, silver_dirs, gold_directory, spark):
    suffix = snapshot_date_str.replace('-', '_')

    attr_df = spark.read.parquet(
        silver_dirs["attributes"] + f"silver_attributes_{suffix}.parquet"
    )
    fin_df = spark.read.parquet(
        silver_dirs["financials"] + f"silver_financials_{suffix}.parquet"
    )
    print(
        f"loaded silver row counts -> "
        f"attributes:{attr_df.count()} "
        f"financials:{fin_df.count()}"
    )

    join_keys = ["Customer_ID", "snapshot_date"]
    df = attr_df.join(fin_df, on=join_keys, how="inner")
    null_counts = df.select([
        F.sum(col(c).isNull().cast("int")).alias(c) for c in df.columns
    ]).collect()[0].asDict()
    nulls_found = {c: v for c, v in null_counts.items() if v > 0}
    print(f"null counts after join: {nulls_found if nulls_found else 'none'}")


    print(f"feature_store_customer row count after join: {df.count()}")

    out_path = gold_directory + f"gold_feature_store_customer_{suffix}.parquet"
    df.write.mode("overwrite").parquet(out_path)
    print("saved to:", out_path)

    return df


def _safe_col_name(s):
    return s.replace(" ", "_").replace("-", "_").replace(",", "")


def discover_customer_categorical_values(gold_customer_directory, spark):
    """One-shot scan over all gold_feature_store_customer parquets to find the
    canonical set of values per categorical column + the canonical set of loan
    types embedded in Type_of_Loan. Used to lock the engineered output schema
    across snapshots."""
    # recursiveFileLookup=true: each per-snapshot "gold_*.parquet" is itself a
    # directory of part files; recursion lets Spark find them all under the
    # parent dir in one read.
    df = (
        spark.read
             .option("recursiveFileLookup", "true")
             .parquet(gold_customer_directory)
    )

    def _distinct_non_null(c):
        return [r[0] for r in df.select(c).distinct().collect() if r[0] is not None]

    # Type_of_Loan parsing: split on ",", trim, strip leading "and ", drop empties
    loan_types_df = (
        df.select(F.coalesce(col("Type_of_Loan"), F.lit("")).alias("tol"))
          .withColumn(
              "types",
              F.transform(
                  F.split(col("tol"), ","),
                  lambda x: F.regexp_replace(F.trim(x), "^and ", ""),
              ),
          )
          .select(F.explode(col("types")).alias("t"))
          .filter(col("t") != "")
          .distinct()
    )
    loan_types = [r["t"] for r in loan_types_df.collect()]

    canonical = {
        "occupations":         sorted(_distinct_non_null("Occupation")),
        "credit_mixes":        sorted(_distinct_non_null("Credit_Mix")),
        "payment_behaviours":  sorted(_distinct_non_null("Payment_Behaviour")),
        "loan_types":          sorted(loan_types),
    }
    print("discovered canonical values:")
    for k, v in canonical.items():
        print(f"  {k}: {v}")
    return canonical


def process_feature_store_customer_engineered_table(
    snapshot_date_str, gold_customer_directory, gold_engineered_directory, spark, canonical
):
    suffix = snapshot_date_str.replace('-', '_')

    filepath = gold_customer_directory + f"gold_feature_store_customer_{suffix}.parquet"
    df = spark.read.parquet(filepath)
    print('loaded from:', filepath, 'row count:', df.count())

    # Leakage drop for the default-prediction use case: Interest_Rate is the
    # bank's own risk-based price, set after underwriting — target proxy.
    df = df.drop("Interest_Rate")

    # one-hot encode three categorical columns
    ohe_cols = [
        ("Occupation",        canonical["occupations"]),
        ("Credit_Mix",        canonical["credit_mixes"]),
        ("Payment_Behaviour", canonical["payment_behaviours"]),
    ]
    for col_name, values in ohe_cols:
        for v in values:
            df = df.withColumn(
                f"{col_name}_{_safe_col_name(v)}",
                F.when(col(col_name) == v, 1).otherwise(0).cast(IntegerType()),
            )
        df = df.drop(col_name)

    # Type_of_Loan -> per-type counts
    df = df.withColumn(
        "_loan_types_array",
        F.transform(
            F.split(F.coalesce(col("Type_of_Loan"), F.lit("")), ","),
            lambda x: F.regexp_replace(F.trim(x), "^and ", ""),
        ),
    )
    for lt in canonical["loan_types"]:
        df = df.withColumn(
            f"{_safe_col_name(lt).lower()}_type",
            F.size(F.filter(col("_loan_types_array"), lambda x: x == lt)).cast(IntegerType()),
        )
    df = df.drop("_loan_types_array", "Type_of_Loan")

    out_path = gold_engineered_directory + f"gold_feature_store_customer_engineered_{suffix}.parquet"
    df.write.mode("overwrite").parquet(out_path)
    print("saved to:", out_path)

    return df


def process_label_store_table(snapshot_date_str, silver_lms_directory, gold_directory, spark, dpd=30, mob=6):
    suffix = snapshot_date_str.replace('-', '_')

    filepath = silver_lms_directory + f"silver_lms_{suffix}.parquet"
    df = spark.read.parquet(filepath)
    print('loaded from:', filepath, 'row count:', df.count())

    df = df.filter(col("mob") == mob)
    df = df.withColumn("label", F.when(col("dpd") >= dpd, 1).otherwise(0).cast(IntegerType()))
    df = df.withColumn("label_def", F.lit(f"{dpd}dpd_{mob}mob").cast(StringType()))
    df = df.select("loan_id", "Customer_ID", "label", "label_def", "snapshot_date")

    out_path = gold_directory + f"gold_label_store_{suffix}.parquet"
    df.write.mode("overwrite").parquet(out_path)
    print('saved to:', out_path)

    return df
