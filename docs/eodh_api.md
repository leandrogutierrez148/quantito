# EOD Historical Data (EODHD) API Documentation in Quantito

This document provides a detailed guide on how the EODHD API is used in the **Quantito** project, including the available endpoints, query parameters, response structures with real examples, and the description of the fields provided.

---

## 1. Authentication and Global Parameters

All queries to the EODHD API require authentication via an API token. In addition, global parameters are set for the output format.

- **API Token (`api_token`)**: Must be provided in the query string of each request. In Quantito, this is retrieved from the `EODHD_API_TOKEN` environment variable.
- **Format (`fmt`)**: By default, EODHD can return CSV data. To facilitate handling in Python and BigQuery, Quantito explicitly requests `fmt=json`.
- **Rate Limits**:
  EODHD responds with HTTP headers indicating the status of the quota:
  - `X-RateLimit-Limit`: Maximum number of daily requests allowed.
  - `X-RateLimit-Remaining`: Remaining requests for the current day.

---

## 2. Endpoints Used

Quantito consumes three main endpoints from EODHD:
1. **Real-Time Quotes**
2. **US Delayed Quotes**
3. **End-Of-Day (EOD) Historical Data**

---

### 2.1. Real-Time Quotes

Obtains live, real-time quote updates for stocks and Forex pairs to track active market movements.

- **Data Frequency**: Price updates are delivered on a minute-by-minute basis.
- **Forex Coverage**: Features a 1-minute delay for 1,100+ Forex pairs.
- **Standard Delay**: Under the free/standard tier, quote snapshots for stock symbols are delayed by 15-20 minutes.

- **Endpoint URL**: `https://eodhd.com/api/real-time/<SYMBOL>`
- **Method**: `GET`
- **Query Parameters**:
  - `s` (optional): Comma-separated list of additional symbols for batch queries.
  - `api_token` (required): EODHD authentication token.
  - `fmt` (required): Response format (`json`).

#### Query Example
```http
GET https://eodhd.com/api/real-time/GOOGL.US?s=AAPL.US,GOOGL.US&api_token=YOUR_API_TOKEN&fmt=json
```

#### Response Structure (JSON Array)
The API returns an array of objects, where each object represents a ticker quote.
```json
[
  {
    "code": "GOOGL.US",
    "timestamp": 1783456080,
    "gmtoffset": 0,
    "open": 369.07,
    "high": 373.16,
    "low": 365.5,
    "close": 367.03,
    "volume": 23930981,
    "previousClose": 366.46,
    "change": 0.57,
    "change_p": 0.1555
  },
  {
    "code": "AAPL.US",
    "timestamp": 1783456140,
    "gmtoffset": 0,
    "open": 315.29,
    "high": 315.48,
    "low": 310.15,
    "close": 310.66,
    "volume": 42013892,
    "previousClose": 312.66,
    "change": -2.0,
    "change_p": -0.6397
  }
]
```

#### Response Field Descriptions
| Field | Type | Description |
| :--- | :--- | :--- |
| `code` | String | The stock ticker symbol (e.g., `AAPL.US`). |
| `timestamp` | Integer | Unix epoch timestamp of the quote. |
| `gmtoffset` | Integer | GMT offset in seconds. |
| `open` | Float | Opening price of the ticker for the current session. |
| `high` | Float | Highest price reached in the current session. |
| `low` | Float | Lowest price recorded in the current session. |
| `close` | Float | Last/closing price. |
| `volume` | Integer | Share volume traded during the current session. |
| `previousClose` | Float | Closing price of the previous trading session. |
| `change` | Float | Absolute price change compared to the previous close (`close - previousClose`). |
| `change_p` | Float | Percentage price change compared to the previous close. |

---

### 2.2. US Delayed Quotes

Retrieves a detailed, exchange-compliant quote snapshot for US stocks in a single request. Rather than just returning the last trade price, it bundles essential valuation metrics and technical indicators.

- **Key Information**: Last trade event times, bid/ask prices with sizes, timestamps, and intraday changes.
- **Technical Indicators**: Bundles rolling averages (50, 100, and 200 days) along with 52-week extremes.
- **Reference Fields**: Provides fundamental metrics (market cap, P/E ratio, dividends, and issuer details).
- **Batch Support**: Supports querying multiple symbols simultaneously.

- **Endpoint URL**: `https://eodhd.com/api/us-quote-delayed`
- **Method**: `GET`
- **Query Parameters**:
  - `s` (required): Comma-separated list of symbols (e.g., `AAPL.US,GOOGL.US`).
  - `api_token` (required): EODHD authentication token.
  - `fmt` (required): Response format (`json`).

#### Query Example
```http
GET https://eodhd.com/api/us-quote-delayed?s=AAPL.US,GOOGL.US&api_token=YOUR_API_TOKEN&fmt=json
```

#### Response Structure (JSON Object)
Returns an object with the structure `{"meta": ..., "data": {"TICKER": {...}}}`.
```json
{
  "meta": {
    "count": 2
  },
  "data": {
    "AAPL.US": {
      "symbol": "AAPL.US",
      "exchange": "XNAS",
      "isoExchange": "XNAS",
      "bzExchange": "NASDAQ",
      "otcMarket": "",
      "otcTier": "",
      "type": "STOCK",
      "name": "Apple",
      "companyStandardName": "Apple Inc",
      "description": "Apple Inc. - Common Stock",
      "sector": "Information Technology",
      "industry": "Technology Hardware, Storage & Peripherals",
      "open": 294.12,
      "high": 309.42,
      "low": 293.68,
      "bidPrice": 304.01,
      "askPrice": 317.0,
      "askSize": 0,
      "bidSize": 0,
      "size": 10890738,
      "bidTime": 1783036800000,
      "askTime": 1783036800000,
      "lastTradePrice": 308.45,
      "lastTradeTime": 1783036792291,
      "volume": 75400626,
      "change": -0.18,
      "changePercent": -0.06,
      "previousClosePrice": 308.63,
      "previousCloseDate": "2026-07-01 17:00:00",
      "fiftyDayAveragePrice": 292.6738,
      "hundredDayAveragePrice": 276.5905,
      "twoHundredDayAveragePrice": 270.3318,
      "averageVolume": 53022885,
      "fiftyTwoWeekHigh": 317.4,
      "fiftyTwoWeekLow": 201.5,
      "marketCap": 4528397633000,
      "sharesOutstanding": 14681140000,
      "sharesFloat": 14672068878,
      "pe": 35.639225,
      "forwardPE": 30.9598,
      "dividendYield": 0.0037,
      "dividend": 1.08,
      "payoutRatio": 0.1259,
      "ethPrice": 308.45,
      "ethVolume": 4495918,
      "ethTime": 1783036792291,
      "currency": "USD",
      "issuerName": "Apple Inc",
      "primary": true,
      "shortDescription": "Ordinary Shares",
      "issuerShortName": "Apple",
      "timestamp": 1783051140
    }
  }
}
```

#### Response Field Descriptions
- **Identification**:
  - `symbol`: Unique ticker (e.g., `AAPL.US`).
  - `exchange` / `isoExchange` / `bzExchange`: Exchange codes (e.g., `XNAS`, `NASDAQ`).
  - `type`: Asset type (e.g., `STOCK`).
  - `name` / `companyStandardName`: Company name.
  - `description` / `shortDescription`: Description of the financial instrument.
- **Classification**:
  - `sector`: Industrial sector (e.g., `Information Technology`).
  - `industry`: Subsector/Industry (e.g., `Technology Hardware, Storage & Peripherals`).
- **Session Prices**:
  - `open`, `high`, `low`: Opening, high, and low prices of the current session.
  - `bidPrice` / `askPrice` / `bidSize` / `askSize`: Bid/Ask pricing and size information.
  - `lastTradePrice` / `lastTradeTime`: Price and epoch timestamp (milliseconds) of the last executed transaction.
  - `volume`: Cumulative volume of the trading session.
- **Changes and History**:
  - `change` / `changePercent`: Absolute and percentage change relative to the previous close.
  - `previousClosePrice` / `previousCloseDate`: Price and date of the last close.
- **Technical & Historical Statistics**:
  - `fiftyDayAveragePrice` / `hundredDayAveragePrice` / `twoHundredDayAveragePrice`: 50, 100, and 200-day moving averages.
  - `averageVolume`: Average daily trading volume.
  - `fiftyTwoWeekHigh` / `fiftyTwoWeekLow`: Highest and lowest price within the last 52 weeks.
- **Fundamentals & Valuation**:
  - `marketCap`: Total market capitalization in the asset's currency.
  - `sharesOutstanding` / `sharesFloat`: Total shares outstanding and free-float shares.
  - `pe` / `forwardPE`: Current and forward Price-to-Earnings ratios.
  - `dividend` / `dividendYield` / `payoutRatio`: Dividend per share, dividend yield, and dividend payout ratio.
- **Other**:
  - `currency`: Currency code (e.g., `USD`).
  - `timestamp`: Unix epoch timestamp of the quote.

---

### 2.3. End-Of-Day (EOD) Historical Data

Retrieves historical OHLCV (Open, High, Low, Close, Volume) data for a wide range of assets, including stocks, ETFs, mutual funds, indices, Forex, and cryptocurrencies.

- **Flexible Intervals**: Supports retrieving daily, weekly, or monthly historical series.
- **Deep History**: Offers historical data reaching back over 30 years for many instruments.
- **Adjusted Prices**: Provides `adjusted_close` prices (accounting for splits and dividend distributions), which are recommended for quantitative analysis and modeling.

- **Endpoint URL**: `https://eodhd.com/api/eod/<SYMBOL>`
- **Method**: `GET`
- **Query Parameters**:
  - `api_token` (required): EODHD authentication token.
  - `fmt` (required): Response format (`json`).
  - `from` (optional): Start date for the historical series (format `YYYY-MM-DD`).
  - `to` (optional): End date for the historical series (format `YYYY-MM-DD`).
  - `period` (optional): Data frequency. Accepted values: `d` (daily), `w` (weekly), `m` (monthly).

#### Query Example
```http
GET https://eodhd.com/api/eod/AAPL.US?api_token=YOUR_API_TOKEN&fmt=json
```

#### Response Structure (JSON Array)
Returns a chronological list of trading sessions with their respective prices and volumes.
```json
[
  {
    "date": "2025-07-07",
    "open": 212.68,
    "high": 216.23,
    "low": 208.8,
    "close": 209.95,
    "adjusted_close": 209.1204,
    "volume": 50229000
  },
  {
    "date": "2025-07-08",
    "open": 210.1,
    "high": 211.43,
    "low": 208.45,
    "close": 210.01,
    "adjusted_close": 209.1801,
    "volume": 42848900
  }
]
```

#### Response Field Descriptions
| Field | Type | Description |
| :--- | :--- | :--- |
| `date` | String | Trading session date in `YYYY-MM-DD` format. |
| `open` | Float | Opening price at the start of the session. |
| `high` | Float | Highest price reached during the session. |
| `low` | Float | Lowest price recorded during the session. |
| `close` | Float | Raw closing price of the session. |
| `adjusted_close` | Float | Closing price adjusted for stock splits and dividend distributions. Recommended for quantitative analysis. |
| `volume` | Integer | Shares volume traded during the session. |
