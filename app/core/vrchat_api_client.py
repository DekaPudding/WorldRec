from __future__ import annotations

import base64
import http.cookiejar
import json
import urllib.parse
import urllib.error
import urllib.request


class VrchatApiError(Exception):
    pass


class VrchatAuthRequiredError(VrchatApiError):
    pass


class VrchatRateLimitError(VrchatApiError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class VrchatApiClient:
    _ALLOWED_DOWNLOAD_HOST_SUFFIXES = ("vrchat.cloud", "vrcdn.cloud")
    _MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
    _MAX_REDIRECTS = 5

    def __init__(
        self,
        base_url: str = "https://api.vrchat.cloud/api/1",
        timeout_seconds: float = 12.0,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.username = username
        self.password = password
        self.cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def get_world(self, world_id: str) -> dict:
        if not world_id:
            raise VrchatApiError("world_id が空です。")
        return self._request_json(f"/worlds/{world_id}")

    def login(self, username: str, password: str) -> dict:
        normalized_username = (username or "").strip()
        if not normalized_username or not password:
            raise VrchatApiError("ユーザー名とパスワードを入力してください。")
        self.cookie_jar.clear()
        self.username = normalized_username
        self.password = password
        try:
            return self._request_json("/auth/user", use_basic_auth=True)
        finally:
            # Basic認証送信後はメモリ上の平文パスワードを保持しない。
            self.password = None

    def verify_two_factor(self, method: str, code: str) -> dict:
        normalized_method = self._normalize_two_factor_method(method)
        if not normalized_method:
            raise VrchatApiError("未対応の2段階認証方式です。")

        normalized_code = (code or "").strip()
        if not normalized_code:
            raise VrchatApiError("2FAコードを入力してください。")
        if normalized_method == "totp" and (
            not normalized_code.isdigit() or len(normalized_code) != 6
        ):
            raise VrchatApiError("認証アプリの6桁コードを入力してください。")

        return self._request_json(
            f"/auth/twofactorauth/{normalized_method}/verify",
            method="POST",
            json_body={"code": normalized_code},
        )

    def get_current_user(self) -> dict:
        return self._request_json("/auth/user")

    def find_world_id_by_name(self, world_name: str, limit: int = 10) -> str | None:
        query = (world_name or "").strip()
        if not query:
            return None

        params = urllib.parse.urlencode(
            {
                "search": query,
                "n": max(1, min(limit, 100)),
                "offset": 0,
            }
        )
        data = self._request_data(f"/worlds?{params}")
        if not isinstance(data, list):
            return None

        normalized_query = query.lower()
        first_world_id: str | None = None
        for item in data:
            if not isinstance(item, dict):
                continue
            world_id = item.get("id")
            name = item.get("name")
            if not isinstance(world_id, str):
                continue
            if first_world_id is None:
                first_world_id = world_id
            if isinstance(name, str) and name.strip().lower() == normalized_query:
                return world_id

        return first_world_id

    def download_bytes(self, url: str) -> bytes:
        current_url = self._validate_download_url(url)

        for _ in range(self._MAX_REDIRECTS + 1):
            request = urllib.request.Request(current_url, headers=self._build_headers())
            try:
                with self._open_without_redirect(request) as response:
                    self._validate_download_url(response.geturl())
                    return self._read_limited_bytes(response)
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get("Location") if exc.headers else None
                    if not location:
                        raise VrchatApiError("サムネイル取得失敗: リダイレクト先が不正です。") from exc
                    next_url = urllib.parse.urljoin(current_url, str(location).strip())
                    current_url = self._validate_download_url(next_url)
                    continue
                raise VrchatApiError(f"サムネイル取得失敗: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise VrchatApiError(f"サムネイル取得失敗: {exc.reason}") from exc

        raise VrchatApiError("サムネイル取得失敗: リダイレクト回数が上限を超えました。")

    def _request_json(
        self,
        path: str,
        method: str = "GET",
        json_body: dict | None = None,
        use_basic_auth: bool = False,
    ) -> dict:
        data = self._request_data(
            path,
            method=method,
            json_body=json_body,
            use_basic_auth=use_basic_auth,
        )
        if not isinstance(data, dict):
            raise VrchatApiError("VRChat API 応答形式が不正です。")
        return data

    def _request_data(
        self,
        path: str,
        method: str = "GET",
        json_body: dict | None = None,
        use_basic_auth: bool = False,
    ):
        data_bytes = None
        if json_body is not None:
            data_bytes = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers=self._build_headers(use_basic_auth=use_basic_auth),
            data=data_bytes,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = self._parse_retry_after_seconds(exc.headers)
                if retry_after is not None:
                    raise VrchatRateLimitError(
                        f"VRChat API が混雑しています。{retry_after} 秒待って再試行してください。",
                        retry_after_seconds=retry_after,
                    ) from exc
                raise VrchatRateLimitError(
                    "VRChat API が混雑しています。しばらく待って再試行してください。"
                ) from exc
            if exc.code in (401, 403):
                raise VrchatAuthRequiredError("VRChat API 認証が必要です。") from exc
            raise VrchatApiError(f"VRChat API エラー: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise VrchatApiError(f"VRChat API 接続失敗: {exc.reason}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise VrchatApiError("VRChat API 応答のJSON解析に失敗しました。") from exc
        return data

    def _build_headers(self, use_basic_auth: bool = False) -> dict[str, str]:
        headers = {"User-Agent": "WorldRec/1.0", "Accept": "application/json"}
        if use_basic_auth and self.username and self.password:
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        if use_basic_auth:
            headers["Content-Type"] = "application/json"
        return headers

    def _validate_download_url(self, url: str) -> str:
        value = (url or "").strip()
        if not value:
            raise VrchatApiError("サムネイル取得失敗: URLが空です。")

        parsed = urllib.parse.urlparse(value)
        if parsed.scheme.lower() != "https":
            raise VrchatApiError("サムネイル取得失敗: HTTPS以外のURLは許可されていません。")

        host = (parsed.hostname or "").lower()
        if not host:
            raise VrchatApiError("サムネイル取得失敗: ホスト名が不正です。")

        if not self._is_allowed_download_host(host):
            raise VrchatApiError("サムネイル取得失敗: 許可されていない配信元です。")

        return value

    def _is_allowed_download_host(self, host: str) -> bool:
        for suffix in self._ALLOWED_DOWNLOAD_HOST_SUFFIXES:
            if host == suffix or host.endswith(f".{suffix}"):
                return True
        return False

    def _open_without_redirect(self, request: urllib.request.Request):
        class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
                return None

        opener = urllib.request.build_opener(_NoRedirectHandler)
        return opener.open(request, timeout=self.timeout_seconds)

    def _read_limited_bytes(self, response) -> bytes:
        content_length_header = response.headers.get("Content-Length")
        if content_length_header is not None:
            try:
                content_length = int(str(content_length_header).strip())
                if content_length > self._MAX_DOWNLOAD_BYTES:
                    raise VrchatApiError(
                        "サムネイル取得失敗: サイズ上限を超えています。"
                    )
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > self._MAX_DOWNLOAD_BYTES:
                raise VrchatApiError("サムネイル取得失敗: サイズ上限を超えています。")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _parse_retry_after_seconds(headers) -> int | None:
        if headers is None:
            return None
        retry_after_raw = headers.get("Retry-After")
        if retry_after_raw is None:
            return None
        try:
            value = int(str(retry_after_raw).strip())
            if value < 0:
                return None
            return value
        except ValueError:
            return None

    @staticmethod
    def _normalize_two_factor_method(method: str | None) -> str | None:
        value = (method or "").strip().lower()
        if value in ("totp",):
            return "totp"
        if value in ("emailotp", "email_otp", "emailotp2", "email"):
            return "emailotp"
        if value in ("otp",):
            return "otp"
        return None
