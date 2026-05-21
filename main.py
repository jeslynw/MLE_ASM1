import os
from datetime import datetime

import pyspark
import utils.data_processing_bronze_table
import utils.data_processing_silver_table
import utils.data_processing_gold_table


# initialize spark session
spark = pyspark.sql.SparkSession.builder \
    .appName("dev") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

# set up config
start_date_str = "2023-01-01"
end_date_str = "2024-12-01"


# generate list of dates to process
def generate_first_of_month_dates(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    first_of_month_dates = []
    current_date = datetime(start_date.year, start_date.month, 1)

    while current_date <= end_date:
        first_of_month_dates.append(current_date.strftime("%Y-%m-%d"))
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)

    return first_of_month_dates


dates_str_lst = generate_first_of_month_dates(start_date_str, end_date_str)
print(dates_str_lst)

# bronze, silver, gold directories
bronze_clickstream_directory = "datamart/bronze/feature_clickstream/"
bronze_attributes_directory = "datamart/bronze/features_attributes/"
bronze_financials_directory = "datamart/bronze/features_financials/"
bronze_lms_directory = "datamart/bronze/lms/"
silver_clickstream_directory = "datamart/silver/feature_clickstream/"
silver_attributes_directory = "datamart/silver/features_attributes/"
silver_financials_directory = "datamart/silver/features_financials/"
silver_lms_directory = "datamart/silver/lms/"
gold_feature_store_clickstream_directory          = "datamart/gold/feature_store_clickstream/"
gold_feature_store_customer_directory             = "datamart/gold/feature_store_customer/"
gold_feature_store_customer_engineered_directory  = "datamart/gold/feature_store_customer_engineered/"
gold_label_store_directory = "datamart/gold/label_store/"

# silver inputs for the gold feature_store_customer join (attributes + financials)
silver_dirs = {
    "attributes": silver_attributes_directory,
    "financials": silver_financials_directory,
}

# (dataset_name, source_csv, bronze_dir, silver_dir, date_format_in_source)
datasets = [
    ("clickstream", "data/feature_clickstream.csv", bronze_clickstream_directory, silver_clickstream_directory, "dd/MM/yyyy"),
    ("attributes", "data/features_attributes.csv", bronze_attributes_directory,  silver_attributes_directory,  "dd/MM/yyyy"),
    ("financials", "data/features_financials.csv", bronze_financials_directory,  silver_financials_directory,  "dd/MM/yyyy"),
    ("lms", "data/lms_loan_daily.csv", bronze_lms_directory, silver_lms_directory, "yyyy-MM-dd"),
]

for _, _, bronze_dir, silver_dir, _ in datasets:
    os.makedirs(bronze_dir, exist_ok=True)
    os.makedirs(silver_dir, exist_ok=True)
os.makedirs(gold_feature_store_clickstream_directory, exist_ok=True)
os.makedirs(gold_feature_store_customer_directory, exist_ok=True)
os.makedirs(gold_feature_store_customer_engineered_directory, exist_ok=True)
os.makedirs(gold_label_store_directory, exist_ok=True)


# # run bronze
# for date_str in dates_str_lst:
#     for name, src, bronze_dir, _, date_fmt in datasets:
#         utils.data_processing_bronze_table.process_bronze_table(date_str, src, bronze_dir, name, spark, date_fmt)


# # run silver
# for date_str in dates_str_lst:
#     for name, _, bronze_dir, silver_dir, _ in datasets:
#         utils.data_processing_silver_table.process_silver_table(date_str, name, bronze_dir, silver_dir, spark)


# run gold cleaned joins / passthroughs / label
for date_str in dates_str_lst:
    utils.data_processing_gold_table.process_feature_store_clickstream_table(
        date_str, silver_clickstream_directory, gold_feature_store_clickstream_directory, spark,
    )
    utils.data_processing_gold_table.process_feature_store_customer_table(
        date_str, silver_dirs, gold_feature_store_customer_directory, spark,
    )
    utils.data_processing_gold_table.process_label_store_table(
        date_str, silver_lms_directory, gold_label_store_directory, spark, dpd=30, mob=6,
    )

# run gold feature-engineered customer table (OHE + Type_of_Loan counts)
canonical = utils.data_processing_gold_table.discover_customer_categorical_values(
    gold_feature_store_customer_directory, spark,
)
for date_str in dates_str_lst:
    utils.data_processing_gold_table.process_feature_store_customer_engineered_table(
        date_str,
        gold_feature_store_customer_directory,
        gold_feature_store_customer_engineered_directory,
        spark,
        canonical,
    )
