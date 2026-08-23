import datetime
import logging
import os

import requests

logger = logging.getLogger(__name__)


def create_bq_table_if_not_exists(client, dataset_ref, table_id):
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    schema = [
        bigquery.SchemaField("code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("gmtoffset", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("open", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("high", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("low", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("close", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("volume", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("previousClose", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("change", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("change_p", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
    ]

    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
    except NotFound:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        logger.info(f"Created BigQuery table: {table_id}")


def store_data(data):
    bq_dataset = os.getenv("BIGQUERY_DATASET")
    if not bq_dataset:
        logger.info("BIGQUERY_DATASET is not configured. Skipping BigQuery storage.")
        return

    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    client = bigquery.Client()
    dataset_ref = client.dataset(bq_dataset)

    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = os.getenv("BIGQUERY_LOCATION", "US")
        client.create_dataset(dataset)
        logger.info(f"Created BigQuery dataset: {bq_dataset}")

    create_bq_table_if_not_exists(client, dataset_ref, "real_time_quotes")

    now_str = datetime.datetime.now(datetime.UTC).isoformat()
    rows = []
    for row in data:
        new_row = dict(row)
        new_row["inserted_at"] = now_str
        rows.append(new_row)

    table_ref = dataset_ref.table("real_time_quotes")
    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        raise RuntimeError(f"Errors inserting real-time quotes into BigQuery: {errors}")

    logger.info(f"Inserted {len(rows)} real-time quotes into BigQuery.")


def run():
    logger.info("Starting Real-Time Quotes Pipeline.")
    api_token = os.getenv("EODHD_API_TOKEN")
    symbols_str = os.getenv("SYMBOLS", "AAPL.US,GOOGL.US")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    if not api_token:
        raise RuntimeError("EODHD_API_TOKEN is not set.")

    if not symbols:
        logger.warning("No symbols to retrieve.")
        return

    main_symbol = symbols[0]
    additional_symbols = ",".join(symbols)

    real_time_url = f"https://eodhd.com/api/real-time/{main_symbol}"
    logger.info(f"Retrieving real-time quotes for symbols: {symbols}")

    try:
        response = requests.get(
            real_time_url, params={"s": additional_symbols, "api_token": api_token, "fmt": "json"}
        )
        response.raise_for_status()
        res_json = response.json()

        raw_quotes = []
        if isinstance(res_json, list):
            raw_quotes = res_json
        elif isinstance(res_json, dict):
            raw_quotes = [res_json]

    except Exception:
        raise RuntimeError("Error fetching real-time quotes.") from None

    processed_quotes = []
    for quote in raw_quotes:
        if not isinstance(quote, dict):
            continue
        code = quote.get("code")
        close = quote.get("close")
        if not code or close is None:
            logger.warning(f"Skipping malformed real-time quote: {quote}")
            continue

        processed_quotes.append(quote)

    if processed_quotes:
        store_data(processed_quotes)
    else:
        logger.warning("No valid quotes to store.")


if __name__ == "__main__":
    run()
