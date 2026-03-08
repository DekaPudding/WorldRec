from __future__ import annotations

import io
import unittest
import urllib.error
from unittest.mock import patch

from app.core.vrchat_api_client import VrchatApiClient, VrchatApiError


class _FakeResponse:
    def __init__(self, url: str, body: bytes, content_length: str | None = None) -> None:
        self._url = url
        self._buffer = io.BytesIO(body)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class VrchatApiClientSecurityTest(unittest.TestCase):
    def test_download_blocks_redirect_to_disallowed_host(self) -> None:
        client = VrchatApiClient(timeout_seconds=1.0)
        redirect_error = urllib.error.HTTPError(
            url="https://assets.vrchat.cloud/img.png",
            code=302,
            msg="Found",
            hdrs={"Location": "https://example.com/malicious.png"},
            fp=None,
        )

        with patch.object(client, "_open_without_redirect", side_effect=redirect_error):
            with self.assertRaises(VrchatApiError):
                client.download_bytes("https://assets.vrchat.cloud/img.png")

    def test_download_fails_when_redirect_limit_exceeded(self) -> None:
        client = VrchatApiClient(timeout_seconds=1.0)
        redirect_error = urllib.error.HTTPError(
            url="https://assets.vrchat.cloud/img.png",
            code=302,
            msg="Found",
            hdrs={"Location": "https://assets.vrchat.cloud/next.png"},
            fp=None,
        )

        side_effects = [redirect_error] * (client._MAX_REDIRECTS + 1)  # noqa: SLF001
        with patch.object(client, "_open_without_redirect", side_effect=side_effects):
            with self.assertRaisesRegex(VrchatApiError, "リダイレクト回数が上限を超えました"):
                client.download_bytes("https://assets.vrchat.cloud/img.png")

    def test_download_respects_size_limit_even_without_content_length(self) -> None:
        client = VrchatApiClient(timeout_seconds=1.0)
        too_large = b"a" * (client._MAX_DOWNLOAD_BYTES + 1)  # noqa: SLF001
        response = _FakeResponse(url="https://assets.vrchat.cloud/img.png", body=too_large)

        with patch.object(client, "_open_without_redirect", return_value=response):
            with self.assertRaisesRegex(VrchatApiError, "サイズ上限を超えています"):
                client.download_bytes("https://assets.vrchat.cloud/img.png")


if __name__ == "__main__":
    unittest.main()
