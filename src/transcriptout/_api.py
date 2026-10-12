"""`YouTubeTranscriptApi`: the youtube-transcript-api interface, served by TranscriptOut.

Migration is the import line:

    from youtube_transcript_api import YouTubeTranscriptApi   # before
    from transcriptout import YouTubeTranscriptApi            # after

The key comes from `api_key=` or the TRANSCRIPTOUT_API_KEY environment variable. Fetching goes
through TranscriptOut, so there is nothing to proxy and nothing for YouTube to block on your side.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ._errors import CouldNotRetrieveTranscript, NoTranscriptFound, TranscriptsDisabled
from ._http import STATUS_FOR_CODE, Http, error_for
from ._transcripts import FetchedTranscript, TranscriptList, fetched_from_data

# One batch job takes at most this many videos (the API's ceiling); longer lists run as several jobs.
BATCH_MAX = 4000


@dataclass
class BatchResult:
    """What `fetch_many` returns: transcripts and errors, both keyed by video id."""

    transcripts: Dict[str, FetchedTranscript] = field(default_factory=dict)
    errors: Dict[str, CouldNotRetrieveTranscript] = field(default_factory=dict)
    job_ids: List[str] = field(default_factory=list)


class YouTubeTranscriptApi:
    def __init__(self, api_key: Optional[str] = None, *, base_url: Optional[str] = None,
                 timeout: float = 60.0, max_retries: int = 3, segment: Optional[int] = None,
                 proxy_config=None, http_client=None):
        """
        :param api_key: your TranscriptOut key (`sk_…`). Defaults to TRANSCRIPTOUT_API_KEY.
        :param base_url: API root, defaults to https://api.transcriptout.com.
        :param timeout: seconds per HTTP request.
        :param max_retries: retries on 429 and 503, honouring Retry-After. Those are not charged.
        :param segment: maximum characters per snippet for auto-generated tracks (20–5000). The API
            default is 180, which groups words into readable sentences. Manual tracks keep the
            author's own lines unless this is set.
        :param proxy_config: accepted for compatibility and ignored, there is nothing to proxy.
        :param http_client: an optional `requests.Session` to send requests with.
        """
        self._http = Http(api_key, base_url, timeout, max_retries, session=http_client)
        self._segment = segment

    # ---- the youtube-transcript-api 1.x interface ---------------------------------------------

    def fetch(self, video_id: str, languages: Iterable[str] = ("en",),
              preserve_formatting: bool = False) -> FetchedTranscript:
        """The transcript in the first of `languages` the video has, manual tracks before generated
        ones in each language, as in the original.

        Costs one credit when the first language exists. Otherwise one more call lists the video's
        tracks to pick the next language, so a miss never turns into a request per language.
        """
        langs = list(languages) or ["en"]
        try:
            return self._fetch_track(video_id, langs[0], None)
        except NoTranscriptFound:
            if len(langs) == 1:
                raise
        return self.list(video_id).find_transcript(langs[1:]).fetch()

    def list(self, video_id: str) -> TranscriptList:
        """The tracks the video has. One credit."""
        data = self._http.request("GET", "/v1/video", params={"id": video_id}, video_id=video_id)
        tracks = (data or {}).get("available_langs") or []
        if not tracks:
            raise TranscriptsDisabled(video_id)
        return TranscriptList.build(self, (data or {}).get("video_id") or video_id, tracks)

    # ---- batch: what the original makes you write as a loop -----------------------------------

    def fetch_many(self, video_ids: Sequence[str], language: str = "en", *, kind: Optional[str] = None,
                   poll_interval: float = 3.0, timeout: Optional[float] = None,
                   on_progress: Optional[Callable[[Dict], None]] = None) -> BatchResult:
        """Transcripts for many videos through the batch endpoint, up to 4,000 per job.

        One request submits the whole list, TranscriptOut works through it at your rate limit and
        retries what it can, and the results are collected here. Longer lists run as several jobs in
        a row. One credit per video; videos that could not be delivered for reasons on our side are
        refunded. Needs a user key (`sk_…`).

        :param language: one language for the whole job.
        :param kind: "manual" or "auto"; by default the manual track, else the generated one.
        :param on_progress: called with the job status dict after every poll.
        """
        ids = list(dict.fromkeys(v for v in video_ids if v))
        result = BatchResult()
        deadline = time.monotonic() + timeout if timeout else None
        for start in range(0, len(ids), BATCH_MAX):
            chunk = ids[start:start + BATCH_MAX]
            body = {"videos": chunk, "lang": language, "format": "json"}
            if kind:
                body["kind"] = kind
            if self._segment:
                body["segment"] = self._segment
            job = self._http.request("POST", "/v1/transcripts", json=body,
                                     headers={"Idempotency-Key": str(uuid.uuid4())})
            job_id = job["job_id"]
            result.job_ids.append(job_id)
            self._wait(job_id, poll_interval, deadline, on_progress)
            self._collect(job_id, language, result)
        return result

    def _wait(self, job_id: str, poll_interval: float, deadline: Optional[float],
              on_progress: Optional[Callable[[Dict], None]]) -> None:
        while True:
            status = self._http.request("GET", f"/v1/transcripts/{job_id}")
            if on_progress:
                on_progress(status)
            if status.get("status") in ("done", "cancelled"):
                return
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(f"Batch job {job_id} is still running; results stay available for three days")
            time.sleep(poll_interval)

    def _collect(self, job_id: str, language: str, result: BatchResult) -> None:
        token = None
        while True:
            params = {"limit": 500}
            if token:
                params["next_page_token"] = token
            page = self._http.request("GET", f"/v1/transcripts/{job_id}/results", params=params)
            for item in page.get("results") or []:
                vid = item.get("video_id", "")
                if item.get("status") == "ready":
                    result.transcripts[vid] = fetched_from_data(item, language)
                else:
                    result.errors[vid] = error_for(int(item.get("http_status") or STATUS_FOR_CODE.get(item.get("code"), 500)),
                                                   item.get("code"),
                                                   str(item.get("detail") or ""), vid)
            token = page.get("next_page_token")
            if not page.get("has_more") or not token:
                return

    # ---- the static methods removed in youtube-transcript-api 1.2.0 ---------------------------

    @staticmethod
    def get_transcript(video_id: str, languages: Iterable[str] = ("en",), proxies=None, cookies=None,
                       preserve_formatting: bool = False) -> List[Dict]:
        """The pre-1.0 call, still working here: a list of {text, start, duration} dicts."""
        return YouTubeTranscriptApi().fetch(video_id, languages).to_raw_data()

    @staticmethod
    def get_transcripts(video_ids: Sequence[str], languages: Iterable[str] = ("en",),
                        continue_after_error: bool = False, proxies=None, cookies=None,
                        preserve_formatting: bool = False) -> Tuple[Dict[str, List[Dict]], List[str]]:
        """The pre-1.0 call for many videos, now one batch job instead of a loop."""
        api = YouTubeTranscriptApi()
        langs = list(languages) or ["en"]
        batch = api.fetch_many(video_ids, langs[0])
        data = {vid: t.to_raw_data() for vid, t in batch.transcripts.items()}
        failed: List[str] = []
        for vid, err in batch.errors.items():
            # The batch takes one language; a video missing it gets the rest of the list one by one.
            if isinstance(err, NoTranscriptFound) and len(langs) > 1:
                try:
                    data[vid] = api.fetch(vid, langs[1:]).to_raw_data()
                    continue
                except CouldNotRetrieveTranscript as e:
                    err = e
            if not continue_after_error:
                raise err
            failed.append(vid)
        return data, failed

    @staticmethod
    def list_transcripts(video_id: str, proxies=None, cookies=None) -> TranscriptList:
        return YouTubeTranscriptApi().list(video_id)

    # ---- internals -----------------------------------------------------------------------------

    def _fetch_track(self, video_id: str, language: str, kind: Optional[str]) -> FetchedTranscript:
        params = {"video": video_id, "lang": language, "format": "json"}
        if kind:
            params["kind"] = kind
        if self._segment:
            params["segment"] = self._segment
        try:
            data = self._http.request("GET", "/v1/transcript", params=params, video_id=video_id)
        except NoTranscriptFound:
            raise NoTranscriptFound(video_id, [language]) from None
        return fetched_from_data(data, language)
