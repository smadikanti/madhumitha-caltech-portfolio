"""Tests for the TAP API extraction module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from stellar_pipeline.config import ApiConfig
from stellar_pipeline.exceptions import ExtractionError
from stellar_pipeline.extract import TAPClient, build_adql_query
from stellar_pipeline.models import TAP_COLUMNS


class TestBuildAdqlQuery:
    def test_default_query_includes_all_columns(self) -> None:
        query = build_adql_query()
        for col in TAP_COLUMNS:
            assert col in query

    def test_default_query_has_where_clause(self) -> None:
        query = build_adql_query()
        assert "WHERE default_flag=1" in query

    def test_limit_appended_when_specified(self) -> None:
        query = build_adql_query(limit=100)
        assert "TOP 100" in query

    def test_no_limit_when_none(self) -> None:
        query = build_adql_query(limit=None)
        assert "TOP" not in query


class TestTAPClient:
    @pytest.fixture
    def api_config(self) -> ApiConfig:
        return ApiConfig(
            base_url="https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            timeout=10,
            max_retries=2,
            backoff_base=1.0,
            backoff_max=2.0,
        )

    @patch("stellar_pipeline.extract.requests.Session")
    def test_successful_fetch(
        self, mock_session_cls: MagicMock, api_config: ApiConfig, sample_api_rows: list[dict]
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_rows
        mock_response.raise_for_status.return_value = None

        session_instance = MagicMock()
        session_instance.get.return_value = mock_response
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)
        records = client.fetch()

        assert len(records) == len(sample_api_rows)
        assert records[0].pl_name == "Kepler-22 b"
        assert records[1].pl_name == "TRAPPIST-1 e"

    @patch("stellar_pipeline.extract.requests.Session")
    def test_empty_response_returns_empty_list(
        self, mock_session_cls: MagicMock, api_config: ApiConfig
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None

        session_instance = MagicMock()
        session_instance.get.return_value = mock_response
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)
        records = client.fetch()

        assert records == []

    @patch("stellar_pipeline.extract.time.sleep")
    @patch("stellar_pipeline.extract.requests.Session")
    def test_retries_on_timeout(
        self,
        mock_session_cls: MagicMock,
        mock_sleep: MagicMock,
        api_config: ApiConfig,
        sample_api_rows: list[dict],
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_rows
        mock_response.raise_for_status.return_value = None

        session_instance = MagicMock()
        session_instance.get.side_effect = [
            requests.exceptions.Timeout("timed out"),
            mock_response,
        ]
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)
        records = client.fetch()

        assert len(records) == len(sample_api_rows)
        assert session_instance.get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("stellar_pipeline.extract.time.sleep")
    @patch("stellar_pipeline.extract.requests.Session")
    def test_raises_after_all_retries_exhausted(
        self,
        mock_session_cls: MagicMock,
        mock_sleep: MagicMock,
        api_config: ApiConfig,
    ) -> None:
        session_instance = MagicMock()
        session_instance.get.side_effect = requests.exceptions.Timeout("timed out")
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)

        with pytest.raises(ExtractionError, match="failed after"):
            client.fetch()

        assert session_instance.get.call_count == api_config.max_retries + 1

    @patch("stellar_pipeline.extract.requests.Session")
    def test_raises_on_client_error_without_retry(
        self, mock_session_cls: MagicMock, api_config: ApiConfig
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 400
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        session_instance = MagicMock()
        session_instance.get.return_value = mock_response
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)

        with pytest.raises(ExtractionError, match="Client error"):
            client.fetch()

        assert session_instance.get.call_count == 1

    @patch("stellar_pipeline.extract.requests.Session")
    def test_raises_on_non_list_json_response(
        self, mock_session_cls: MagicMock, api_config: ApiConfig
    ) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "bad query"}
        mock_response.raise_for_status.return_value = None

        session_instance = MagicMock()
        session_instance.get.return_value = mock_response
        mock_session_cls.return_value = session_instance

        client = TAPClient(api_config)

        with pytest.raises(ExtractionError, match="Expected JSON array"):
            client.fetch()

    @patch("stellar_pipeline.extract.requests.Session")
    def test_context_manager_closes_session(
        self, mock_session_cls: MagicMock, api_config: ApiConfig
    ) -> None:
        session_instance = MagicMock()
        mock_session_cls.return_value = session_instance

        with TAPClient(api_config):
            pass

        session_instance.close.assert_called_once()
