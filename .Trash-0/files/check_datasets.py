import pyspark
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("check").master("local[*]").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

gold_dirs = {
    "feature_store_clickstream":         "datamart/gold/feature_store_clickstream/",
    "feature_store_customer":            "datamart/gold/feature_store_customer/",
    "feature_store_customer_engineered": "datamart/gold/feature_store_customer_engineered/",
    "label_store":                       "datamart/gold/label_store/",
}

print(f"\n{'Dataset':<40} {'Rows':>10} {'Columns':>10}")
print("-" * 62)
for name, path in gold_dirs.items():
    df = spark.read.option("recursiveFileLookup", "true").parquet(path)
    print(f"{name:<40} {df.count():>10,} {len(df.columns):>10}")

spark.stop()
