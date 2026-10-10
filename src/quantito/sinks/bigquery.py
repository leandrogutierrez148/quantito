import datetime
import json
import logging
import os

from quantito.models import Signal
from quantito.sinks.base import BaseSignalSink

logger = logging.getLogger(__name__)


class BigQuerySignalSink(BaseSignalSink):
    """
    Persists signals into Google Cloud BigQuery 'signals' table.
    """

    def __init__(self, dataset_name: str | None = None, table_id: str = "signals"):
        self.dataset_name = dataset_name or os.getenv("BIGQUERY_DATASET")
        self.table_id = table_id
        self._client = None
        self._table_ref = None

    def _init_bigquery(self):
        if not self.dataset_name:
            return False

        try:
            from google.api_core.exceptions import NotFound
            from google.cloud import bigquery

            self._client = bigquery.Client()
            dataset_ref = self._client.dataset(self.dataset_name)

            # Ensure table exists
            schema = [
                bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("signal_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("price", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("strategy_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("confidence", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            ]

            self._table_ref = dataset_ref.table(self.table_id)
            try:
                self._client.get_table(self._table_ref)
            except NotFound:
                table = bigquery.Table(self._table_ref, schema=schema)
                self._client.create_table(table)
                logger.info(f"Created BigQuery table for signals: {self.table_id}")

            return True
        except ImportError:
            logger.warning(
                "google-cloud-bigquery is not installed. Skipping BigQuery signal persistence."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize BigQuerySignalSink: {e}")
            return False

    def send(self, signals: list[Signal]) -> None:
        if not signals:
            return

        if not self._client and not self._init_bigquery():
            return

        now_str = datetime.datetime.now(datetime.UTC).isoformat()
        rows = []
        for s in signals:
            rows.append(
                {
                    "symbol": s.symbol,
                    "signal_type": s.signal_type.value,
                    "price": s.price,
                    "strategy_name": s.strategy_name,
                    "confidence": s.confidence,
                    "metadata": json.dumps(s.metadata) if s.metadata else None,
                    "timestamp": s.timestamp.isoformat(),
                    "inserted_at": now_str,
                }
            )

        try:
            errors = self._client.insert_rows_json(self._table_ref, rows)
            if errors:
                logger.error(f"BigQuerySignalSink insert errors: {errors}")
            else:
                logger.info(
                    f"Successfully inserted {len(rows)} signals into BigQuery ({self.table_id})."
                )
        except Exception as e:
            logger.error(f"BigQuerySignalSink insert failed: {e}")
