from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import httpx

from .config import Settings


class SupabaseError(RuntimeError):
    pass


class Supabase:
    def __init__(self, settings: Settings):
        self.settings = settings
        key = settings.secret_key.get_secret_value()
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        self.client = httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0), headers=self.headers)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, f"{self.settings.rest_url}/{path.lstrip('/')}", **kwargs)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase {method} {path}: {response.status_code} {response.text[:800]}")
        return response

    def select(self, table: str, *, select: str = "*", params: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        query = {"select": select, **(params or {})}
        if limit is not None:
            query["limit"] = str(limit)
        return self._request("GET", table, params=query).json()

    def insert(self, table: str, rows: dict[str, Any] | Iterable[dict[str, Any]], *, returning: bool = True) -> list[dict[str, Any]]:
        headers = {"Prefer": "return=representation" if returning else "return=minimal"}
        response = self._request("POST", table, json=rows, headers=headers)
        return response.json() if returning and response.content else []

    def upsert(self, table: str, rows: dict[str, Any] | Iterable[dict[str, Any]], *, on_conflict: str) -> list[dict[str, Any]]:
        response = self._request(
            "POST", table, params={"on_conflict": on_conflict}, json=rows,
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        return response.json()

    def update(self, table: str, values: dict[str, Any], *, filters: dict[str, str]) -> list[dict[str, Any]]:
        response = self._request("PATCH", table, params=filters, json=values, headers={"Prefer": "return=representation"})
        return response.json() if response.content else []

    def delete(self, table: str, *, filters: dict[str, str]) -> None:
        self._request("DELETE", table, params=filters, headers={"Prefer": "return=minimal"})

    def upload(self, bucket: str, object_path: str, file_path: Path, content_type: str) -> str:
        endpoint = f"{self.settings.project_url.rstrip('/')}/storage/v1/object/{bucket}/{object_path}"
        with file_path.open("rb") as stream:
            response = self.client.post(endpoint, content=stream, headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"})
        if response.status_code >= 400:
            raise SupabaseError(f"Storage upload failed: {response.status_code} {response.text[:500]}")
        return f"{self.settings.project_url.rstrip('/')}/storage/v1/object/public/{bucket}/{object_path}"
