"""Transcript objects with the same shape as youtube-transcript-api 1.x.

`FetchedTranscript`, `FetchedTranscriptSnippet`, `Transcript` and `TranscriptList` keep the attribute
and method names of the original, so code that iterates snippets, reads `.text` / `.start` /
`.duration`, calls `.to_raw_data()` or picks a track from the list keeps working unchanged.
"""
from dataclasses import asdict, dataclass
from itertools import chain
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List

from ._errors import NoTranscriptFound, NotTranslatable

if TYPE_CHECKING:
    from ._api import YouTubeTranscriptApi


@dataclass
class FetchedTranscriptSnippet:
    text: str
    start: float
    duration: float


@dataclass
class FetchedTranscript:
    snippets: List[FetchedTranscriptSnippet]
    video_id: str
    language: str
    language_code: str
    is_generated: bool

    def __iter__(self) -> Iterator[FetchedTranscriptSnippet]:
        return iter(self.snippets)

    def __getitem__(self, index) -> FetchedTranscriptSnippet:
        return self.snippets[index]

    def __len__(self) -> int:
        return len(self.snippets)

    def to_raw_data(self) -> List[Dict]:
        return [asdict(snippet) for snippet in self]


def fetched_from_data(data: Dict, fallback_language: str = "") -> FetchedTranscript:
    """Builds a FetchedTranscript from what GET /v1/transcript (or a batch item) puts in `data`."""
    code = data.get("language") or fallback_language
    kind = data.get("kind") or "manual"
    name = code
    for track in data.get("available_langs") or []:
        if track.get("code") == code and track.get("kind") == kind:
            name = track.get("name") or code
            break
    snippets = [
        FetchedTranscriptSnippet(text=s.get("text", ""), start=float(s.get("start", 0.0)),
                                 duration=float(s.get("duration", 0.0)))
        for s in data.get("transcript") or []
    ]
    return FetchedTranscript(snippets=snippets, video_id=data.get("video_id", ""), language=name,
                             language_code=code, is_generated=(kind == "auto"))


class Transcript:
    """One track of a video. Nothing is downloaded until `fetch()` is called."""

    def __init__(self, api: "YouTubeTranscriptApi", video_id: str, language: str, language_code: str,
                 is_generated: bool):
        self._api = api
        self.video_id = video_id
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated
        # Translation through YouTube is not offered by TranscriptOut yet.
        self.translation_languages: List = []

    def fetch(self, preserve_formatting: bool = False) -> FetchedTranscript:
        return self._api._fetch_track(self.video_id, self.language_code,
                                      "auto" if self.is_generated else "manual")

    def __str__(self) -> str:
        return f'{self.language_code} ("{self.language}")'

    @property
    def is_translatable(self) -> bool:
        return False

    def translate(self, language_code: str) -> "Transcript":
        raise NotTranslatable(self.video_id)


class TranscriptList:
    """The tracks a video has, manual ones first, as in the original."""

    def __init__(self, video_id: str, manually_created_transcripts: Dict[str, Transcript],
                 generated_transcripts: Dict[str, Transcript], translation_languages: List = None):
        self.video_id = video_id
        self._manually_created_transcripts = manually_created_transcripts
        self._generated_transcripts = generated_transcripts
        self._translation_languages = translation_languages or []

    @staticmethod
    def build(api: "YouTubeTranscriptApi", video_id: str, available_langs: List[Dict]) -> "TranscriptList":
        manual: Dict[str, Transcript] = {}
        generated: Dict[str, Transcript] = {}
        for track in available_langs or []:
            code = track.get("code")
            if not code:
                continue
            auto = track.get("kind") == "auto"
            target = generated if auto else manual
            target.setdefault(code, Transcript(api, video_id, track.get("name") or code, code, auto))
        return TranscriptList(video_id, manual, generated)

    def __iter__(self) -> Iterator[Transcript]:
        return chain(self._manually_created_transcripts.values(), self._generated_transcripts.values())

    def find_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find(language_codes, [self._manually_created_transcripts, self._generated_transcripts])

    def find_generated_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find(language_codes, [self._generated_transcripts])

    def find_manually_created_transcript(self, language_codes: Iterable[str]) -> Transcript:
        return self._find(language_codes, [self._manually_created_transcripts])

    def _find(self, language_codes: Iterable[str], dicts: List[Dict[str, Transcript]]) -> Transcript:
        codes = list(language_codes)
        for code in codes:
            for d in dicts:
                if code in d:
                    return d[code]
        raise NoTranscriptFound(self.video_id, codes, self)

    def __str__(self) -> str:
        def describe(items):
            lines = [f" - {t}" for t in items]
            return "\n".join(lines) if lines else "None"

        return (
            f"For this video ({self.video_id}) transcripts are available in the following languages:\n\n"
            f"(MANUALLY CREATED)\n{describe(self._manually_created_transcripts.values())}\n\n"
            f"(GENERATED)\n{describe(self._generated_transcripts.values())}"
        )
