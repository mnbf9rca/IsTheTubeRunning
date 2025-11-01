"""Tests for core utility functions."""

from app.core.utils import convert_async_db_url_to_sync


class TestConvertAsyncDbUrlToSync:
    """Tests for convert_async_db_url_to_sync function."""

    def test_converts_asyncpg_to_sync(self) -> None:
        """Test conversion of asyncpg URL to sync URL."""
        async_url = "postgresql+asyncpg://user:pass@localhost:5432/dbname"
        expected = "postgresql://user:pass@localhost:5432/dbname"

        result = convert_async_db_url_to_sync(async_url)

        assert result == expected

    def test_preserves_sync_url(self) -> None:
        """Test that sync URLs are returned unchanged."""
        sync_url = "postgresql://user:pass@localhost:5432/dbname"

        result = convert_async_db_url_to_sync(sync_url)

        assert result == sync_url

    def test_preserves_query_parameters(self) -> None:
        """Test that query parameters are preserved."""
        async_url = "postgresql+asyncpg://user:pass@localhost:5432/dbname?ssl=true"
        expected = "postgresql://user:pass@localhost:5432/dbname?ssl=true"

        result = convert_async_db_url_to_sync(async_url)

        assert result == expected

    def test_preserves_fragment(self) -> None:
        """Test that URL fragments are preserved."""
        async_url = "postgresql+asyncpg://user:pass@localhost:5432/dbname#fragment"
        expected = "postgresql://user:pass@localhost:5432/dbname#fragment"

        result = convert_async_db_url_to_sync(async_url)

        assert result == expected
