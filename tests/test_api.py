"""Offline tests: a fake session stands in for the API, nothing leaves the machine."""
import json

import pytest

from transcriptout import (
    AuthenticationError,
    InsufficientCredits,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)
from transcriptout.formatters import SRTFormatter, TextFormatter, WebVTTFormatter

VID = "dQw4w9WgXcQ"
LANGS = [
    {"code": "en", "kind": "manual", "name": "English"},
    {"code": "en", "kind": "auto", "name": "English (auto-generated)"},
    {"code": "de", "kind": "auto", "name": "German (auto-generated)"},
]


class Resp:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.ok = 200 <= status < 300
        self.reason = "reason"

    def json(self):
        return json.loads(json.dumps(self._body))


class FakeSession:
    """Answers by (method, path) from a queue of responses and records every call."""

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        path = url.split("api.transcriptout.com", 1)[1]
        self.calls.append((method, path, params, json, headers))
        queue = self.routes[(method, path)]
        return queue.pop(0) if len(queue) > 1 else queue[0]


def ok(data):
    return Resp(200, {"ok": True, "request_id": "req_1", "data": data})


def err(status, code, detail):
    return Resp(status, {"ok": False, "code": code, "detail": detail, "request_id": "req_2"})


def track(lang="en", kind="manual"):
    return {"video_id": VID, "language": lang, "kind": kind, "available_langs": LANGS,
            "transcript": [{"text": "hello", "start": 0.0, "duration": 1.5},
                           {"text": "world", "start": 1.5, "duration": 2.0}]}


def api(routes):
    s = FakeSession(routes)
    return YouTubeTranscriptApi("sk_test", http_client=s), s


def test_fetch_first_language_is_one_call():
    a, s = api({("GET", "/v1/transcript"): [ok(track())]})
    t = a.fetch(VID)
    assert [x.text for x in t] == ["hello", "world"]
    assert t.language == "English" and t.language_code == "en" and t.is_generated is False
    assert t.to_raw_data()[1] == {"text": "world", "start": 1.5, "duration": 2.0}
    assert len(s.calls) == 1
    method, path, params, _, headers = s.calls[0]
    assert params == {"video": VID, "lang": "en", "format": "json"}
    assert headers["Authorization"] == "Bearer sk_test"


def test_fetch_falls_back_through_the_track_list():
    a, s = api({
        ("GET", "/v1/transcript"): [err(404, "not_found", "No subtitles for requested language"), ok(track("de", "auto"))],
        ("GET", "/v1/video"): [ok({"video_id": VID, "available_langs": LANGS})],
    })
    t = a.fetch(VID, languages=["fr", "de"])
    assert t.language_code == "de" and t.is_generated is True
    assert [c[1] for c in s.calls] == ["/v1/transcript", "/v1/video", "/v1/transcript"]
    assert s.calls[2][2]["kind"] == "auto"


def test_missing_language_raises_no_transcript_found():
    a, _ = api({("GET", "/v1/transcript"): [err(404, "not_found", "No subtitles for requested language")]})
    with pytest.raises(NoTranscriptFound):
        a.fetch(VID, languages=["fr"])


def test_no_subtitles_at_all_is_transcripts_disabled():
    a, _ = api({("GET", "/v1/video"): [ok({"video_id": VID, "available_langs": []})]})
    with pytest.raises(TranscriptsDisabled):
        a.list(VID)


def test_error_codes_map_to_original_exceptions():
    a, _ = api({("GET", "/v1/transcript"): [err(410, "gone", "Video unavailable/removed")]})
    with pytest.raises(VideoUnavailable):
        a.fetch(VID)
    a, _ = api({("GET", "/v1/transcript"): [err(402, "insufficient_credits", "No credits")]})
    with pytest.raises(InsufficientCredits) as e:
        a.fetch(VID)
    assert isinstance(e.value, YouTubeTranscriptApiException)


def test_missing_key_is_reported_before_any_request(monkeypatch):
    monkeypatch.delenv("TRANSCRIPTOUT_API_KEY", raising=False)
    s = FakeSession({})
    with pytest.raises(AuthenticationError):
        YouTubeTranscriptApi(http_client=s).fetch(VID)
    assert s.calls == []


def test_retries_503_and_honours_retry_after(monkeypatch):
    slept = []
    monkeypatch.setattr("transcriptout._http.time.sleep", slept.append)
    a, s = api({("GET", "/v1/transcript"): [Resp(503, {"ok": False, "code": "service_unavailable"},
                                                  {"Retry-After": "2"}), ok(track())]})
    assert len(a.fetch(VID)) == 2
    assert slept == [2.0] and len(s.calls) == 2


def test_list_orders_manual_first():
    a, _ = api({("GET", "/v1/video"): [ok({"video_id": VID, "available_langs": LANGS})]})
    tl = a.list(VID)
    assert [str(t) for t in tl] == ['en ("English")', 'en ("English (auto-generated)")', 'de ("German (auto-generated)")']
    assert tl.find_generated_transcript(["en"]).is_generated is True
    with pytest.raises(NoTranscriptFound):
        tl.find_manually_created_transcript(["de"])


def test_fetch_many_runs_one_job_and_collects_pages(monkeypatch):
    monkeypatch.setattr("transcriptout._api.time.sleep", lambda s: None)
    ready = {"status": "ready", "cache": "HIT", **track()}
    bad = {"status": "error", "video_id": "xxxxxxxxxxx", "code": "not_found", "detail": "No subtitles for this video"}
    a, s = api({
        ("POST", "/v1/transcripts"): [Resp(202, {"ok": True, "data": {"job_id": "j1", "status": "queued"}})],
        ("GET", "/v1/transcripts/j1"): [ok({"status": "running"}), ok({"status": "done"})],
        ("GET", "/v1/transcripts/j1/results"): [ok({"results": [ready], "has_more": True, "next_page_token": "t2"}),
                                                ok({"results": [bad], "has_more": False})],
    })
    r = a.fetch_many([VID, "xxxxxxxxxxx", VID])
    assert list(r.transcripts) == [VID] and isinstance(r.errors["xxxxxxxxxxx"], TranscriptsDisabled)
    post = s.calls[0]
    assert post[3]["videos"] == [VID, "xxxxxxxxxxx"] and "Idempotency-Key" in post[4]
    assert s.calls[-1][2]["next_page_token"] == "t2"


def test_get_transcript_static_still_works(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTOUT_API_KEY", "sk_env")
    s = FakeSession({("GET", "/v1/transcript"): [ok(track())]})
    monkeypatch.setattr("transcriptout._http.requests.Session", lambda: s)
    assert YouTubeTranscriptApi.get_transcript(VID)[0] == {"text": "hello", "start": 0.0, "duration": 1.5}
    assert s.calls[0][4]["Authorization"] == "Bearer sk_env"


def test_formatters():
    a, _ = api({("GET", "/v1/transcript"): [ok(track())]})
    t = a.fetch(VID)
    assert TextFormatter().format_transcript(t) == "hello\nworld"
    assert SRTFormatter().format_transcript(t).startswith("1\n00:00:00,000 --> 00:00:01,500\nhello")
    assert WebVTTFormatter().format_transcript(t).startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nhello")
