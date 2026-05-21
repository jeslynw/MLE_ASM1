from pyspark.sql import functions as F
from pyspark.sql.functions import col, regexp_replace, when
from pyspark.sql.types import StringType, IntegerType, FloatType, DateType


def clean_num(c, sep_swap=False, dtype=FloatType()):
    e = regexp_replace(col(c), "_", "")
    if sep_swap:
        e = regexp_replace(e, ",", ".")
    e = when(e == "", None).otherwise(e)
    return e.cast(dtype)


def tukey_upper_fence(df, column, k=1.5):
    q1, q3 = df.approxQuantile(column, [0.25, 0.75], 0.001)
    return q3 + k * (q3 - q1)


def process_silver_table(snapshot_date_str, dataset_name, bronze_directory, silver_directory, spark):
    partition_name = f"bronze_{dataset_name}_{snapshot_date_str.replace('-', '_')}.csv"
    filepath = bronze_directory + partition_name
    df = spark.read.csv(filepath, header=True, inferSchema=True)
    print("loaded from:", filepath, "row count:", df.count())

    if dataset_name == "clickstream":
        column_type_map = {f"fe_{i}": IntegerType() for i in range(1, 21)}
        column_type_map["Customer_ID"] = StringType()
        column_type_map["snapshot_date"] = DateType()
        for c, t in column_type_map.items():
            df = df.withColumn(c, col(c).cast(t))

    elif dataset_name == "attributes":
        # cleaninig dirty data
        df = (
            df
            .filter(col("SSN") != "#F%$D@*&8")
            .drop("SSN")  # PII
            .filter(col("Occupation") != "_______")
            .withColumn("Age", regexp_replace(col("Age").cast("string"), "[^0-9-]", ""))
            .withColumn("Age", col("Age").cast(IntegerType()))
            .filter((col("Age") >= 18) & (col("Age") <= 70))
            .withColumn("Customer_ID", col("Customer_ID").cast(StringType()))
            .withColumn("snapshot_date", col("snapshot_date").cast(DateType()))
        )

    elif dataset_name == "financials":
        # cleaninig dirty data
        df = (
            df
            .withColumn("Annual_Income", F.round(clean_num("Annual_Income"), 2))
            .withColumn("Monthly_Inhand_Salary", clean_num("Monthly_Inhand_Salary", sep_swap=True))
            .withColumn("Num_of_Loan", clean_num("Num_of_Loan", dtype=IntegerType()))
            .withColumn("Num_of_Delayed_Payment", clean_num("Num_of_Delayed_Payment", dtype=IntegerType()))
            .filter(col("Changed_Credit_Limit") != "_")
            .withColumn("Changed_Credit_Limit", F.round(clean_num("Changed_Credit_Limit"), 2))
            .withColumn("Credit_Utilization_Ratio", clean_num("Credit_Utilization_Ratio", sep_swap=True))
            .withColumn("Outstanding_Debt", clean_num("Outstanding_Debt"))
            .withColumn("Total_EMI_per_month", clean_num("Total_EMI_per_month", sep_swap=True))
            .withColumn("Amount_invested_monthly", clean_num("Amount_invested_monthly"))
            .withColumn("Monthly_Balance", clean_num("Monthly_Balance", sep_swap=True))
            # Type_of_Loan null = customer has zero loans (consistent with Num_of_Loan == 0).
            # Normalize blank/whitespace strings to null so downstream sees one canonical "no loans" form.
            .withColumn("Type_of_Loan",
                F.when(F.trim(col("Type_of_Loan")) == "", None).otherwise(col("Type_of_Loan")))
            .filter(col("Credit_Mix") != "_")
            .filter(col("Payment_Behaviour") != "!@9#%8")
            .filter(col("Monthly_Balance").isNotNull())
        )

        # schema enforcement — lock down types for every column, including ones clean_num skipped
        financials_type_map = {
            "Customer_ID": StringType(),
            "Annual_Income": FloatType(),
            "Monthly_Inhand_Salary": FloatType(),
            "Num_Bank_Accounts": IntegerType(),
            "Num_Credit_Card": IntegerType(),
            "Interest_Rate": IntegerType(),
            "Num_of_Loan": IntegerType(),
            "Type_of_Loan": StringType(),
            "Delay_from_due_date": IntegerType(),
            "Num_of_Delayed_Payment": IntegerType(),
            "Changed_Credit_Limit": FloatType(),
            "Num_Credit_Inquiries": IntegerType(),
            "Credit_Mix": StringType(),
            "Outstanding_Debt": FloatType(),
            "Credit_Utilization_Ratio": FloatType(),
            "Credit_History_Age": StringType(),
            "Payment_of_Min_Amount": StringType(),
            "Total_EMI_per_month": FloatType(),
            "Amount_invested_monthly": FloatType(),
            "Payment_Behaviour": StringType(),
            "Monthly_Balance": FloatType(),
            "snapshot_date": DateType(),
        }
        for c, t in financials_type_map.items():
            df = df.withColumn(c, col(c).cast(t))

        # sanity boundary check, use Tukey 1.5*IQR for max boundary
        range_cols = [
            "Num_Bank_Accounts",
            "Num_Credit_Card",
            "Num_of_Loan",
            "Delay_from_due_date",
            "Num_of_Delayed_Payment",
            "Changed_Credit_Limit",
            "Outstanding_Debt",
            "Num_Credit_Inquiries",
            "Total_EMI_per_month",
            "Amount_invested_monthly",
        ]
        fences = {c: tukey_upper_fence(df, c) for c in range_cols}
        for c, upper in fences.items():
            print(f"  fence  {c:<26} -> between(0, {upper:.2f})")
            df = df.filter(col(c).between(0, upper))

    elif dataset_name == "lms":
        # lifted from MLE/lab_2/utils/data_processing_silver_table.py
        column_type_map = {
            "loan_id": StringType(),
            "Customer_ID": StringType(),
            "loan_start_date": DateType(),
            "tenure": IntegerType(),
            "installment_num": IntegerType(),
            "loan_amt": FloatType(),
            "due_amt": FloatType(),
            "paid_amt": FloatType(),
            "overdue_amt": FloatType(),
            "balance": FloatType(),
            "snapshot_date": DateType(),
        }
        for c, t in column_type_map.items():
            df = df.withColumn(c, col(c).cast(t))

        # derived columns for label definition
        df = df.withColumn("mob", col("installment_num").cast(IntegerType()))
        df = df.withColumn(
            "installments_missed",
            F.ceil(F.try_divide(col("overdue_amt"), col("due_amt"))).cast(IntegerType()),
        ).fillna(0)
        df = df.withColumn(
            "first_missed_date",
            F.when(
                col("installments_missed") > 0,
                F.add_months(col("snapshot_date"), -1 * col("installments_missed")),
            ).cast(DateType()),
        )
        df = df.withColumn(
            "dpd",
            F.when(
                col("overdue_amt") > 0.0,
                F.datediff(col("snapshot_date"), col("first_missed_date")),
            ).otherwise(0).cast(IntegerType()),
        )

    else:
        raise ValueError(f"Unknown dataset_name: {dataset_name}")

    out_name = f"silver_{dataset_name}_{snapshot_date_str.replace('-', '_')}.parquet"
    out_path = silver_directory + out_name
    df.write.mode("overwrite").parquet(out_path)
    print("saved to:", out_path)

    return df
