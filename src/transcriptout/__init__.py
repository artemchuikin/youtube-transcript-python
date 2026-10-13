"""TranscriptOut: youtube-transcript-api, but it works from your server.

    from transcriptout import YouTubeTranscriptApi

    ytt_api = YouTubeTranscriptApi()          # reads TRANSCRIPTOUT_API_KEY
    transcript = ytt_api.fetch("dQw4w9WgXcQ")
    for snippet in transcript:
        print(snippet.start, snippet.text)
"""
# ruff: noqa: F401
from ._api import BatchResult, YouTubeTranscriptApi
from ._errors import (
    AgeRestricted,
    AuthenticationError,
    CookieError,
    CookieInvalid,
    CookiePathInvalid,
    CouldNotRetrieveTranscript,
    FailedToCreateConsentCookie,
    InsufficientCredits,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    NotTranslatable,
    PoTokenRequired,
    RateLimited,
    RequestBlocked,
    ServiceUnavailable,
    TranscriptOutError,
    TranscriptsDisabled,
    TranslationLanguageNotAvailable,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeDataUnparsable,
    YouTubeRequestFailed,
    YouTubeTranscriptApiException,
)
from ._transcripts import FetchedTranscript, FetchedTranscriptSnippet, Transcript, TranscriptList

__version__ = "0.1.3"

__all__ = [
    "YouTubeTranscriptApi",
    "BatchResult",
    "TranscriptList",
    "Transcript",
    "FetchedTranscript",
    "FetchedTranscriptSnippet",
    "YouTubeTranscriptApiException",
    "CookieError",
    "CookiePathInvalid",
    "CookieInvalid",
    "TranscriptsDisabled",
    "NoTranscriptFound",
    "CouldNotRetrieveTranscript",
    "VideoUnavailable",
    "VideoUnplayable",
    "IpBlocked",
    "RequestBlocked",
    "NotTranslatable",
    "TranslationLanguageNotAvailable",
    "FailedToCreateConsentCookie",
    "YouTubeRequestFailed",
    "InvalidVideoId",
    "AgeRestricted",
    "YouTubeDataUnparsable",
    "PoTokenRequired",
    "TranscriptOutError",
    "AuthenticationError",
    "InsufficientCredits",
    "RateLimited",
    "ServiceUnavailable",
]
