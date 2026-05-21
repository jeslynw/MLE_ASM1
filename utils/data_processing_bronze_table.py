from pyspark.sql.functions import col, to_date


def process_bronze_table(snapshot_date_str, source_csv_path, bronze_directory, dataset_name, spark, date_format="dd/MM/yyyy"):
    df = spark.read.csv(source_csv_path, sep=",", header=True, inferSchema=True).withColumn("snapshot_date", to_date(col("snapshot_date"), date_format)).filter(col("snapshot_date") == snapshot_date_str)

    
    print(f"{snapshot_date_str} {dataset_name} row count:", df.count())

    partition_name = f"bronze_{dataset_name}_{snapshot_date_str.replace('-', '_')}.csv"
    filepath = bronze_directory + partition_name
    df.toPandas().to_csv(filepath, index=False)
    print("saved to:", filepath)

    return df
