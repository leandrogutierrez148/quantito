import os
import sys
import logging
import requests
import json

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    api_token = os.getenv("EODHD_API_TOKEN")
    symbols_str = os.getenv("SYMBOLS", "AAPL.US,GOOGL.US")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    if not api_token:
        logging.error("EODHD_API_TOKEN is not set.")
        sys.exit(1)

    if not symbols:
        logging.error("No symbols provided in SYMBOLS env variable.")
        sys.exit(1)

    logging.info("Starting EODHD data retrieval job.")
    logging.info(f"Symbols to query: {symbols}")

    session = requests.Session()

    # 1. Real-Time Quotes
    # We query the first symbol in the path and additional ones in the 's' parameter
    main_symbol = symbols[0]
    additional_symbols = ",".join(symbols)
    real_time_url = f"https://eodhd.com/api/real-time/{main_symbol}"
    
    logging.info("Fetching Real-Time Quotes...")
    try:
        response = session.get(real_time_url, params={
            "s": additional_symbols,
            "api_token": api_token,
            "fmt": "json"
        })
        response.raise_for_status()
        logging.info("Real-Time Quotes response:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching real-time quotes: {e}")

    # 2. US Delayed Quotes
    delayed_url = "https://eodhd.com/api/us-quote-delayed"
    logging.info("Fetching US Delayed Quotes...")
    try:
        response = session.get(delayed_url, params={
            "s": additional_symbols,
            "api_token": api_token,
            "fmt": "json"
        })
        response.raise_for_status()
        logging.info("US Delayed Quotes response:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching US delayed quotes: {e}")

    # 3. End-Of-Day (EOD) Historical Data (for each symbol)
    for symbol in symbols:
        eod_url = f"https://eodhd.com/api/eod/{symbol}"
        logging.info(f"Fetching EOD Historical Data for {symbol}...")
        try:
            response = session.get(eod_url, params={
                "api_token": api_token,
                "fmt": "json"
            })
            response.raise_for_status()
            data = response.json()
            logging.info(f"Successfully retrieved {len(data)} EOD data points for {symbol}.")
            # EOD data can be extremely large, so we print a sample of the first 3 entries
            logging.info(f"Sample EOD Data (First 3 elements) for {symbol}:")
            print(json.dumps(data[:3], indent=2))
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching EOD data for {symbol}: {e}")

    logging.info("Data retrieval job completed successfully.")

if __name__ == "__main__":
    main()
