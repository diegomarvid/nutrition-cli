from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import fdc_api_key
from .database import upsert_food_detail
from .models import FoodCandidate


BASE_URL = "https://api.nal.usda.gov/fdc/v1"
PREFERRED_DATA_TYPES = ["Foundation", "SR Legacy", "Survey (FNDDS)"]
DATA_TYPE_RANK = {
    "Foundation": 0,
    "SR Legacy": 1,
    "Survey (FNDDS)": 2,
    "Branded": 3,
}


class FdcError(RuntimeError):
    pass


@dataclass
class RateLimitInfo:
    limit: int | None = None
    remaining: int | None = None
    retry_after_seconds: int | None = None


class FdcRateLimitError(FdcError):
    def __init__(self, message: str, rate_limit: RateLimitInfo) -> None:
        super().__init__(message)
        self.rate_limit = rate_limit


class FdcClient:
    def __init__(self, api_key: str | None = None, timeout: float = 20) -> None:
        self.api_key = api_key or fdc_api_key()
        self.timeout = timeout

    @property
    def using_demo_key(self) -> bool:
        return self.api_key == "DEMO_KEY"

    def search(self, query: str, limit: int = 8) -> list[FoodCandidate]:
        try:
            payload = self._post(
                "/foods/search",
                payload={
                    "query": query,
                    "pageSize": max(limit * 3, limit),
                    "dataType": PREFERRED_DATA_TYPES,
                },
            )
            foods = payload.get("foods", [])
        except FdcRateLimitError:
            raise
        except FdcError:
            foods = []
        if not foods:
            payload = self._post(
                "/foods/search",
                payload={"query": query, "pageSize": limit},
            )
            foods = payload.get("foods", [])

        candidates = [FoodCandidate.from_fdc(food) for food in foods]
        candidates.sort(
            key=lambda food: (
                DATA_TYPE_RANK.get(food.data_type or "", 9),
                -(food.score or 0),
                food.description,
            )
        )
        return candidates[:limit]

    def detail(self, fdc_id: int) -> dict[str, Any]:
        return self._get(f"/food/{fdc_id}", params=[("api_key", self.api_key)])

    def status_probe(self) -> tuple[dict[str, Any], RateLimitInfo]:
        return self._get_with_rate_limit("/foods/list", params=[("api_key", self.api_key), ("pageSize", 1)])

    def _get(self, path: str, params: list[tuple[str, str | int]]) -> dict[str, Any]:
        payload, _ = self._get_with_rate_limit(path, params)
        return payload

    def _get_with_rate_limit(
        self, path: str, params: list[tuple[str, str | int]]
    ) -> tuple[dict[str, Any], RateLimitInfo]:
        response = requests.get(f"{BASE_URL}{path}", params=params, timeout=self.timeout)
        rate_limit = parse_rate_limit(response)
        if response.status_code >= 400:
            if response.status_code == 429:
                raise FdcRateLimitError(
                    f"FDC rate limit exceeded: {response.status_code} {response.text[:300]}",
                    rate_limit,
                )
            raise FdcError(f"FDC request failed: {response.status_code} {response.text[:300]}")
        payload = response.json()
        if "error" in payload:
            error = payload["error"]
            raise FdcError(f"FDC error: {error.get('code')} {error.get('message')}")
        return payload, rate_limit

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{BASE_URL}{path}",
            params={"api_key": self.api_key},
            json=payload,
            timeout=self.timeout,
        )
        rate_limit = parse_rate_limit(response)
        if response.status_code >= 400:
            if response.status_code == 429:
                raise FdcRateLimitError(
                    f"FDC rate limit exceeded: {response.status_code} {response.text[:300]}",
                    rate_limit,
                )
            raise FdcError(f"FDC request failed: {response.status_code} {response.text[:300]}")
        data = response.json()
        if "error" in data:
            error = data["error"]
            raise FdcError(f"FDC error: {error.get('code')} {error.get('message')}")
        return data


def parse_rate_limit(response: requests.Response) -> RateLimitInfo:
    return RateLimitInfo(
        limit=parse_int_header(response.headers.get("X-RateLimit-Limit")),
        remaining=parse_int_header(response.headers.get("X-RateLimit-Remaining")),
        retry_after_seconds=parse_int_header(response.headers.get("Retry-After")),
    )


def parse_int_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def ensure_food_cached(conn, client: FdcClient, fdc_id: int) -> dict[str, Any]:
    food = client.detail(fdc_id)
    upsert_food_detail(conn, food)
    return food
