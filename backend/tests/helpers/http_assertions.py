"""HTTP response assertion helpers."""

from httpx import Response


def assert_401_unauthorized(
    response: Response,
    expected_detail: str | None = None,
) -> None:
    """
    Assert response is 401 Unauthorized with WWW-Authenticate header per RFC 7235.

    Args:
        response: HTTP response object
        expected_detail: Optional expected error detail message
    """
    assert response.status_code == 401
    assert "www-authenticate" in response.headers
    assert response.headers["www-authenticate"] == "Bearer"

    if expected_detail is not None:
        assert response.json()["detail"] == expected_detail
