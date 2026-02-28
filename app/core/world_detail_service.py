from __future__ import annotations

from dataclasses import dataclass

from app.core.vrchat_api_client import (
    VrchatApiClient,
    VrchatApiError,
    VrchatAuthRequiredError,
    VrchatRateLimitError,
)
from app.models.world_detail_dto import WorldDetail, WorldDetailResponse


@dataclass(slots=True)
class AuthResult:
    success: bool
    requires_two_factor: bool = False
    message: str = ""
    two_factor_method: str | None = None


class WorldDetailService:
    def __init__(self, api_client: VrchatApiClient | None = None) -> None:
        self.api_client = api_client or VrchatApiClient()

    def fetch_detail(self, world_id: str | None, world_name: str) -> WorldDetailResponse:
        target_world_id = (world_id or "").strip() or None
        warning_messages: list[str] = []

        if target_world_id is None:
            try:
                target_world_id = self.api_client.find_world_id_by_name(world_name)
            except VrchatAuthRequiredError:
                return WorldDetailResponse(
                    detail=WorldDetail(
                        world_id=None,
                        world_name=world_name,
                        platforms=[],
                    ),
                    warning_message="VRChat API の認証が必要なためワールド詳細を取得できませんでした。",
                    auth_required=True,
                )
            except VrchatApiError as exc:
                warning_messages.append(str(exc))
            except Exception:
                warning_messages.append("ワールド名からIDの解決に失敗しました。")

        if not target_world_id:
            return WorldDetailResponse(
                detail=WorldDetail(
                    world_id=None,
                    world_name=world_name,
                    description=None,
                    thumbnail_url=None,
                    thumbnail_bytes=None,
                    capacity_bytes=None,
                    platforms=[],
                ),
                warning_message=" / ".join(
                    warning_messages or ["world_id を解決できずワールド詳細を取得できませんでした。"]
                ),
            )

        try:
            data = self.api_client.get_world(target_world_id)
        except VrchatAuthRequiredError:
            return WorldDetailResponse(
                detail=WorldDetail(
                    world_id=target_world_id,
                    world_name=world_name,
                    platforms=[],
                ),
                warning_message="VRChat API の認証が必要なため詳細を取得できませんでした。",
                auth_required=True,
            )
        except VrchatApiError as exc:
            return WorldDetailResponse(
                detail=WorldDetail(
                    world_id=target_world_id,
                    world_name=world_name,
                    platforms=[],
                ),
                warning_message=str(exc),
            )
        except Exception:
            return WorldDetailResponse(
                detail=WorldDetail(
                    world_id=target_world_id,
                    world_name=world_name,
                    platforms=[],
                ),
                warning_message="ワールド詳細の取得に失敗しました。",
            )

        normalized = self._normalize(data, target_world_id, world_name)
        if warning_messages:
            return WorldDetailResponse(detail=normalized, warning_message=" / ".join(warning_messages))
        return WorldDetailResponse(detail=normalized)

    def authenticate_with_password(
        self,
        username: str,
        password: str,
    ) -> AuthResult:
        try:
            login_response = self.api_client.login(username, password)
        except VrchatRateLimitError as exc:
            return AuthResult(success=False, message=str(exc))
        except VrchatApiError as exc:
            return AuthResult(success=False, message=str(exc))
        except Exception:
            return AuthResult(success=False, message="認証に失敗しました。")

        required_method = self._extract_required_two_factor_method(login_response)
        if required_method:
            prompt = self._two_factor_prompt(required_method)
            return AuthResult(
                success=False,
                requires_two_factor=True,
                message=prompt,
                two_factor_method=required_method,
            )

        return self._validate_authenticated_session()

    def complete_two_factor(self, method: str, two_factor_code: str) -> AuthResult:
        normalized_method = "emailotp"
        try:
            self.api_client.verify_two_factor(normalized_method, two_factor_code)
        except VrchatRateLimitError as exc:
            return AuthResult(
                success=False,
                requires_two_factor=False,
                message=str(exc),
                two_factor_method="emailotp",
            )
        except VrchatApiError as exc:
            return AuthResult(
                success=False,
                requires_two_factor=True,
                message=str(exc),
                two_factor_method="emailotp",
            )
        except Exception:
            return AuthResult(
                success=False,
                requires_two_factor=True,
                message="2段階認証に失敗しました。",
                two_factor_method="emailotp",
            )

        return self._validate_authenticated_session()

    def _validate_authenticated_session(self) -> AuthResult:
        try:
            self.api_client.get_current_user()
        except VrchatApiError as exc:
            return AuthResult(success=False, message=str(exc))
        except Exception:
            return AuthResult(success=False, message="認証状態の確認に失敗しました。")

        return AuthResult(success=True, message="認証に成功しました。")

    def _normalize(self, data: dict, world_id: str, fallback_name: str) -> WorldDetail:
        name = str(data.get("name") or fallback_name)
        description_value = data.get("description")
        description = str(description_value) if description_value else None
        thumbnail_url = self._pick_thumbnail_url(data)
        capacity_bytes = self._parse_capacity(data.get("capacity"))
        platforms = self._extract_platforms(data)
        thumbnail_bytes = self._try_download_thumbnail(thumbnail_url)

        return WorldDetail(
            world_id=world_id,
            world_name=name,
            description=description,
            thumbnail_url=thumbnail_url,
            thumbnail_bytes=thumbnail_bytes,
            capacity_bytes=capacity_bytes,
            platforms=platforms,
        )

    def _pick_thumbnail_url(self, data: dict) -> str | None:
        candidates = (
            data.get("thumbnailImageUrl"),
            data.get("imageUrl"),
        )
        for item in candidates:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return None

    def _extract_platforms(self, data: dict) -> list[str]:
        platforms: set[str] = set()

        def add_platform(value: str | None) -> None:
            if not value:
                return
            normalized = value.strip().lower()
            if not normalized:
                return
            if normalized in ("standalonewindows", "windows", "pc"):
                platforms.add("PC")
            elif normalized in ("android", "quest", "androidquest"):
                platforms.add("Android/Quest")
            else:
                platforms.add(value.strip())

        unity_packages = data.get("unityPackages")
        if isinstance(unity_packages, list):
            for package in unity_packages:
                if not isinstance(package, dict):
                    continue
                platform_raw = package.get("platform")
                if isinstance(platform_raw, str):
                    add_platform(platform_raw)

        for field_name in ("platforms", "supportedPlatforms", "publicationPlatforms"):
            field_value = data.get(field_name)
            if isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, str):
                        add_platform(item)

        tags = data.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if not isinstance(tag, str):
                    continue
                lowered = tag.lower()
                if "platform:android" in lowered or "platform_quest" in lowered:
                    add_platform("android")
                if "platform:standalonewindows" in lowered or "platform_windows" in lowered:
                    add_platform("standalonewindows")

        return sorted(platforms)

    @staticmethod
    def _parse_capacity(value) -> int | None:
        try:
            if value is None:
                return None
            capacity = int(value)
            if capacity < 0:
                return None
            return capacity
        except (ValueError, TypeError):
            return None

    def _try_download_thumbnail(self, thumbnail_url: str | None) -> bytes | None:
        if not thumbnail_url:
            return None
        try:
            return self.api_client.download_bytes(thumbnail_url)
        except VrchatApiError:
            return None

    @staticmethod
    def _extract_required_two_factor_method(login_response: dict) -> str | None:
        raw = login_response.get("requiresTwoFactorAuth")
        if raw:
            return "emailotp"
        return None

    @staticmethod
    def _two_factor_prompt(method: str) -> str:
        if method == "emailotp":
            return "メールに届いた認証コードを入力してください。"
        return "メールに届いた認証コードを入力してください。"
