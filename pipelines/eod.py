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
        bigquery.SchemaField("date", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("open", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("high", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("low", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("close", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("adjusted_close", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("volume", "INTEGER", mode="NULLABLE"),
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
    print(f"\n--- ConsoleSinker Output Preview (eod) ---")
    print(f"Sample (First 2 entries out of {len(data)}):")
    print(json.dumps(data[:2], indent=2))
    print("------------------------------------\n")

    # 2. BigQuery Sinker
    bq_dataset = os.getenv("BIGQUERY_DATASET")
    if not bq_dataset:
        logging.info("BIGQUERY_DATASET is not configured. Skipping BigQuery storage.")
        return

    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    client = bigquery.Client()
    dataset_ref = client.dataset(bq_dataset)

    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = os.getenv("BIGQUERY_LOCATION", "US")
        client.create_dataset(dataset)
        logging.info(f"Created BigQuery dataset: {bq_dataset}")

    create_bq_table_if_not_exists(client, dataset_ref, "eod_historical_data")

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = []
    for row in data:
        new_row = {
            "symbol": row.get("symbol"),
            "date": row.get("date"),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "adjusted_close": row.get("adjusted_close"),
            "volume": row.get("volume"),
            "inserted_at": now_str,
        }
        rows.append(new_row)

    table_ref = dataset_ref.table("eod_historical_data")
    chunk_size = 500
    total_inserted = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        errors = client.insert_rows_json(table_ref, chunk)
        if errors:
            raise RuntimeError(f"Errors inserting historical data chunk into BigQuery: {errors}")
        total_inserted += len(chunk)

    logging.info(f"Inserted {total_inserted} EOD historical data rows into BigQuery.")

def run():
    logging.info("Starting EOD Historical Data Pipeline.")
    api_token = os.getenv("EODHD_API_TOKEN")
    symbols_str = os.getenv("SYMBOLS", "AAPL.US,GOOGL.US")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    if not api_token:
        raise RuntimeError("EODHD_API_TOKEN is not set.")

    if not symbols:
        logging.warning("No symbols to retrieve.")
        return

    raw_data = []
    for symbol in symbols:
        eod_url = f"https://eodhd.com/api/eod/{symbol}"
        logging.info(f"Retrieving EOD Historical Data for symbol: {symbol}")

        try:
            response = requests.get(eod_url, params={
                "api_token": api_token,
                "fmt": "json"
            })
            response.raise_for_status()
            symbol_data = response.json()
            
            if isinstance(symbol_data, list):
                logging.info(f"Successfully retrieved {len(symbol_data)} EOD data points for {symbol}.")
                for entry in symbol_data:
                    if isinstance(entry, dict):
                        raw_data.append({**entry, "symbol": symbol})
                        
        except Exception:
            raise RuntimeError(
                f"Error fetching EOD historical data for symbol {symbol}."
            ) from None

    # Processing step
    processed_data = []
    for entry in raw_data:
        symbol = entry.get("symbol")
        date = entry.get("date")
        if not symbol or not date:
            logging.warning(f"Skipping malformed EOD entry: {entry}")
            continue
        processed_data.append(entry)

    # Sort by symbol, then date
    processed_data.sort(key=lambda x: (x["symbol"], x["date"]))

    # Log basic statistics per symbol
    symbol_counts = {}
    for entry in processed_data:
        sym = entry["symbol"]
        symbol_counts[sym] = symbol_counts.get(sym, 0) + 1

    logging.info(f"Processed {len(processed_data)} total EOD entries across {len(symbol_counts)} symbols:")
    for sym, count in symbol_counts.items():
        logging.info(f"  - {sym}: {count} data points")

    if processed_data:
        store_data(processed_data)
    else:
        logging.warning("No valid EOD historical data to store.")

if __name__ == "__main__":
    run()
