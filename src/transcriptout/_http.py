"""The one place that talks to the TranscriptOut API: auth, the response envelope, retries, errors."""
import os
import time
from typing import Any, Dict, Optional

import requests

from ._errors import (
    AgeRestricted,
    AuthenticationError,
    CouldNotRetrieveTranscript,
    InsufficientCredits,
    InvalidVideoId,
    NoTranscriptFound,
    RateLimited,
    ServiceUnavailable,
    TranscriptOutError,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeRequestFailed,
)

DEFAULT_BASE_URL = "https://api.transcriptout.com"
USER_AGENT = "transcriptout-python/0.1.3"

# Statuses that mean "not now" rather than "no": the service says when to come back in Retry-After.
# ⚠️ 502 is NOT here. It means the request reached YouTube and failed there, which is charged, so a
# silent retry would spend a second credit without the caller choosing to.
_RETRY_STATUSES = {429, 503}


class Http:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: float = 60.0, max_retries: int = 3, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.environ.get("TRANSCRIPTOUT_API_KEY")
        self.base_url = (base_url or os.environ.get("TRANSCRIPTOUT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()

    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                json: Any = None, headers: Optional[Dict[str, str]] = None, video_id: str = "") -> Any:
        """Calls the API and returns `data` from the envelope, or raises the matching exception."""
        if not self.api_key:
            raise AuthenticationError(
                "No API key. Pass api_key=... or set TRANSCRIPTOUT_API_KEY. "
                "Get a free key at https://transcriptout.com/dashboard")
        hdrs = {"Authorization": f"Bearer {self.api_key}", "User-Agent": USER_AGENT}
        if headers:
            hdrs.update(headers)
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            resp = self.session.request(method, url, params=params, json=json, headers=hdrs, timeout=self.timeout)
            if resp.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                attempt += 1
                time.sleep(_retry_after(resp, attempt))
                continue
            return _unwrap(resp, video_id)


def _retry_after(resp, attempt: int) -> float:
    try:
        return min(float(resp.headers.get("Retry-After", "")), 60.0)
    except ValueError:
        return min(2.0 ** attempt, 30.0)


def _unwrap(resp, video_id: str) -> Any:
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.ok and isinstance(body, dict) and body.get("ok", True):
        return body.get("data", body)
    code = (body or {}).get("code") if isinstance(body, dict) else None
    detail = (body or {}).get("detail") if isinstance(body, dict) else None
    detail = detail if isinstance(detail, str) else (str(detail) if detail else resp.reason)
    raise error_for(resp.status_code, code, detail, video_id,
                    (body or {}).get("request_id") if isinstance(body, dict) else None)


# Batch results name a refusal by its machine code only, the HTTP status is not part of an item.
STATUS_FOR_CODE = {
    "bad_request": 400, "unauthorized": 401, "insufficient_credits": 402, "forbidden": 403,
    "not_found": 404, "gone": 410, "rate_limited": 429, "unavailable_for_legal_reasons": 451,
    "upstream_error": 502, "service_unavailable": 503,
}


def error_for(status: int, code: Optional[str], detail: str, video_id: str,
              request_id: Optional[str] = None) -> Exception:
    """Maps an API refusal onto the exception youtube-transcript-api users already catch."""
    if status in (401, 403):
        return AuthenticationError(detail or "Unauthorized", status, code, request_id)
    if status == 402:
        return InsufficientCredits(detail or "Insufficient credits", status, code, request_id)
    if status == 429:
        return RateLimited(detail or "Rate limited", status, code, request_id)
    if status == 503:
        return ServiceUnavailable(detail or "Service unavailable", status, code, request_id)
    if status == 400 and video_id:
        return InvalidVideoId(video_id, detail)
    if status == 404 and video_id:
        # "No subtitles for this video" means none at all; any other 404 names a language.
        if detail and "for this video" in detail and "language" not in detail:
            return TranscriptsDisabled(video_id, detail)
        return NoTranscriptFound(video_id)
    if status == 410 and video_id:
        return VideoUnavailable(video_id, detail)
    if status == 451 and video_id:
        return AgeRestricted(video_id, detail)
    if status == 502 and video_id:
        return YouTubeRequestFailed(video_id, detail)
    if video_id and 400 <= status < 500:
        return CouldNotRetrieveTranscript(video_id, detail)
    return TranscriptOutError(detail or f"HTTP {status}", status, code, request_id)
