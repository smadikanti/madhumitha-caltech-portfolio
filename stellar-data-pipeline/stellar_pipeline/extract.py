"""TAP API client for the NASA Exoplanet Archive.

Fetches exoplanet data using ADQL queries against the TAP sync endpoint
with configurable retry logic and exponential backoff with jitter.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests

from stellar_pipeline.config import ApiConfig
from stellar_pipeline.exceptions import ExtractionError
from stellar_pipeline.models import RawExoplanet, TAP_COLUMNS

logger = logging.getLogger(__name__)

DEFAULT_ADQL = (
    "SELECT {columns} FROM ps WHERE default_flag=1"
)


def build_adql_query(limit: Optional[int] = None) -> str:
    """Construct the ADQL query for the TAP service.

    Args:
        limit: Maximum number of rows to return. None for all rows.

    Returns:
        A valid ADQL query string.
    """
    columns = ", ".join(TAP_COLUMNS)
    query = DEFAULT_ADQL.format(columns=columns)
    if limit is not None and limit > 0:
        query += f" ORDER BY pl_name ASC TOP {limit}"
    return query


class TAPClient:
    """Client for the NASA Exoplanet Archive TAP sync endpoint.

    Handles HTTP requests with configurable retry logic using
    exponential backoff with jitter to avoid thundering herd.

    Args:
        config: API configuration with endpoint URL and retry settings.
    """

    def __init__(self, config: ApiConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "StellarDataPipeline/1.0",
        })

    def fetch(self, limit: Optional[int] = None) -> list[RawExoplanet]:
        """Fetch exoplanet records from the TAP API.

        Args:
            limit: Maximum number of records to retrieve.

        Returns:
            List of raw exoplanet records parsed from the API response.

        Raises:
            ExtractionError: If all retry attempts are exhausted or the
                response cannot be parsed.
        """
        query = build_adql_query(limit)
        logger.info(f"Executing ADQL query against {self._config.base_url}")
        logger.debug(f"Query: {query}")

        raw_data = self._request_with_retry(query)
        return self._parse_response(raw_data)

    def _request_with_retry(self, query: str) -> list[dict]:
        """Execute the TAP request with exponential backoff and jitter.

        Args:
            query: ADQL query string.

        Returns:
            Parsed JSON response as a list of dictionaries.

        Raises:
            ExtractionError: After all retries are exhausted.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._session.get(
                    self._config.base_url,
                    params={"query": query, "format": "json"},
                    timeout=self._config.timeout,
                )
                response.raise_for_status()
                data = response.json()

                if not isinstance(data, list):
                    raise ExtractionError(
                        f"Expected JSON array from TAP API, got {type(data).__name__}"
                    )

                logger.info(f"Received {len(data)} records from TAP API")
                return data

            except requests.exceptions.Timeout as exc:
                last_exception = exc
                logger.warning(
                    f"Request timed out (attempt {attempt + 1}/{self._config.max_retries + 1})"
                )
            except requests.exceptions.ConnectionError as exc:
                last_exception = exc
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self._config.max_retries + 1}): {exc}"
                )
            except requests.exceptions.HTTPError as exc:
                last_exception = exc
                status = exc.response.status_code if exc.response is not None else "unknown"
                if isinstance(status, int) and 400 <= status < 500 and status != 429:
                    raise ExtractionError(
                        f"Client error {status} from TAP API: {exc}"
                    ) from exc
                logger.warning(
                    f"HTTP {status} (attempt {attempt + 1}/{self._config.max_retries + 1})"
                )
            except (ValueError, KeyError) as exc:
                raise ExtractionError(
                    f"Failed to parse TAP API response: {exc}"
                ) from exc

            if attempt < self._config.max_retries:
                delay = self._backoff_delay(attempt)
                logger.info(f"Retrying in {delay:.1f}s")
                time.sleep(delay)

        raise ExtractionError(
            f"TAP API request failed after {self._config.max_retries + 1} attempts: {last_exception}"
        )

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Uses full jitter: uniform random between 0 and the exponential cap.
        This distributes retry storms better than fixed exponential backoff.
        """
        exponential = min(
            self._config.backoff_max,
            self._config.backoff_base ** (attempt + 1),
        )
        return random.uniform(0, exponential)

    @staticmethod
    def _parse_response(raw_data: list[dict]) -> list[RawExoplanet]:
        """Convert raw API dictionaries into typed dataclass instances.

        Args:
            raw_data: List of dictionaries from the JSON response.

        Returns:
            List of RawExoplanet records.

        Raises:
            ExtractionError: If a record cannot be parsed.
        """
        records: list[RawExoplanet] = []
        for idx, row in enumerate(raw_data):
            try:
                records.append(RawExoplanet.from_dict(row))
            except (TypeError, ValueError) as exc:
                logger.warning(f"Skipping malformed record at index {idx}: {exc}")
        return records

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> TAPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
