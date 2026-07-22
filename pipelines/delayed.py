import os
import sys
import logging
import requests
import json
import datetime

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def create_bq_table_if_not_exists(client, dataset_ref, table_id):
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    schema = [
        bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("exchange", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("open", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("high", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("low", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("lastTradePrice", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("volume", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    
    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
    except NotFound:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        logging.info(f"Created BigQuery table: {table_id}")

def store_data(data):
    # 1. Console Preview Sinker
    print(f"\n--- ConsoleSinker Output Preview (delayed) ---")
    print(f"Sample (First 2 entries out of {len(data)}):")
    print(json.dumps(data[:2], indent=2))
    print("------------------------------------\n")

    # 2. BigQuery Sinker
    bq_dataset = os.getenv("BIGQUERY_DATASET")
    if not bq_dataset:
        logging.info("BIGQUERY_DATASET is not configured. Skipping BigQuery storage.")
        return

    try:
        from google.cloud import bigquery
        from google.api_core.exceptions import NotFound
        
        client = bigquery.Client()
        dataset_ref = client.dataset(bq_dataset)
        
        # Ensure dataset exists
        try:
            client.get_dataset(dataset_ref)
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = os.getenv("BIGQUERY_LOCATION", "US")
            client.create_dataset(dataset)
            logging.info(f"Created BigQuery dataset: {bq_dataset}")

        create_bq_table_if_not_exists(client, dataset_ref, "delayed_quotes")
        
        now_str = datetime.datetime.utcnow().isoformat()
        rows = []
        for row in data:
            new_row = {
                "symbol": row.get("symbol"),
                "exchange": row.get("exchange"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "lastTradePrice": row.get("lastTradePrice"),
                "volume": row.get("volume"),
                "timestamp": row.get("timestamp"),
                "inserted_at": now_str,
            }
            rows.append(new_row)

        table_ref = dataset_ref.table("delayed_quotes")
        errors = client.insert_rows_json(table_ref, rows)
        if errors:
            logging.error(f"Errors inserting delayed quotes into BigQuery: {errors}")
        else:
            logging.info(f"Inserted {len(rows)} delayed quotes into BigQuery.")
            
    except ImportError:
        logging.warning("google-cloud-bigquery is not installed. Skipping BigQuery storage.")
    except Exception as e:
        logging.error(f"Failed storing data to BigQuery: {e}")

def run():
    logging.info("Starting US Delayed Quotes Pipeline.")
    api_token = os.getenv("EODHD_API_TOKEN")
    symbols_str = os.getenv("SYMBOLS", "AAPL.US,GOOGL.US")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    if not api_token:
        logging.error("EODHD_API_TOKEN is not set.")
        sys.exit(1)

    if not symbols:
        logging.warning("No symbols to retrieve.")
        return

    additional_symbols = ",".join(symbols)
    delayed_url = "https://eodhd.com/api/us-quote-delayed"
    logging.info(f"Retrieving delayed quotes for symbols: {symbols}")

    try:
        response = requests.get(delayed_url, params={
            "s": additional_symbols,
            "api_token": api_token,
            "fmt": "json"
        })
        response.raise_for_status()
        res_json = response.json()
        
        raw_quotes = []
        if isinstance(res_json, dict) and "data" in res_json:
            raw_quotes = list(res_json["data"].values())
            
    except Exception as e:
        logging.error(f"Error fetching US delayed quotes: {e}")
        sys.exit(1)

    # Processing step
    processed_quotes = []
    above_50_day_avg_count = 0
    total_valid = 0

    for quote in raw_quotes:
        if not isinstance(quote, dict):
            continue
        symbol = quote.get("symbol")
        last_trade = quote.get("lastTradePrice")
        if not symbol or last_trade is None:
            logging.warning(f"Skipping malformed delayed quote: {quote}")
            continue

        processed_quotes.append(quote)
        total_valid += 1
        
        fifty_day_avg = quote.get("fiftyDayAveragePrice")
        if fifty_day_avg is not None:
            try:
                if float(last_trade) > float(fifty_day_avg):
                    above_50_day_avg_count += 1
            except (ValueError, TypeError):
                pass

    logging.info(f"Processed {total_valid} valid delayed quotes.")
    if total_valid > 0:
        logging.info(f"Stocks trading above their 50-day average: {above_50_day_avg_count}/{total_valid}")

    if processed_quotes:
        store_data(processed_quotes)
    else:
        logging.warning("No valid quotes to store.")

if __name__ == "__main__":
    run()
