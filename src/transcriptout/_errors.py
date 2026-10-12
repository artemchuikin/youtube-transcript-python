"""Exceptions, under the same names youtube-transcript-api uses.

The point of the package is that `except NoTranscriptFound:` and friends keep working after the import
line changes, so every name the original exports exists here and sits in the same place in the
hierarchy. A few of them (`RequestBlocked`, `IpBlocked`, the cookie and proxy errors) are never raised
by us, because the blocking they describe happens on our side and is handled there. They are kept so
that code catching them still imports.

Errors that only exist because there is a service in between (a bad key, an empty balance) derive from
`TranscriptOutError`, which is itself a `YouTubeTranscriptApiException`, so a broad `except` written
for the original still catches them.
"""
from typing import Iterable, Optional


class YouTubeTranscriptApiException(Exception):
    pass


class CookieError(YouTubeTranscriptApiException):
    pass


class CookiePathInvalid(CookieError):
    pass


class CookieInvalid(CookieError):
    pass


class CouldNotRetrieveTranscript(YouTubeTranscriptApiException):
    """A transcript for this video could not be delivered. `cause` says why."""

    CAUSE_MESSAGE = ""

    def __init__(self, video_id: str, detail: Optional[str] = None):
        self.video_id = video_id
        self.detail = detail
        super().__init__(self._build_error_message())

    def _build_error_message(self) -> str:
        message = f"Could not retrieve a transcript for the video https://www.youtube.com/watch?v={self.video_id}!"
        cause = self.cause
        if cause:
            message += f" This is most likely caused by:\n\n{cause}"
        return message

    @property
    def cause(self) -> str:
        return self.CAUSE_MESSAGE or (self.detail or "")


class YouTubeDataUnparsable(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "The data returned for this video could not be parsed"


class YouTubeRequestFailed(CouldNotRetrieveTranscript):
    """The request reached YouTube and failed there. TranscriptOut already retried it."""

    CAUSE_MESSAGE = ""


class VideoUnplayable(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "The video is unplayable"


class VideoUnavailable(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "The video is no longer available"


class InvalidVideoId(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "You provided an invalid video id or URL"


class RequestBlocked(CouldNotRetrieveTranscript):
    """Never raised by TranscriptOut. Kept so that code catching it still imports."""

    CAUSE_MESSAGE = "YouTube is blocking requests from your IP"


class IpBlocked(RequestBlocked):
    """Never raised by TranscriptOut. Kept so that code catching it still imports."""


class TranscriptsDisabled(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "Subtitles are disabled for this video"


class AgeRestricted(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "This video is age, members or login restricted"


class NotTranslatable(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "Translation of transcripts is not supported by TranscriptOut yet"


class TranslationLanguageNotAvailable(CouldNotRetrieveTranscript):
    CAUSE_MESSAGE = "The requested translation language is not available"


class FailedToCreateConsentCookie(CouldNotRetrieveTranscript):
    """Never raised by TranscriptOut. Kept so that code catching it still imports."""


class PoTokenRequired(CouldNotRetrieveTranscript):
    """Never raised by TranscriptOut. Kept so that code catching it still imports."""


class NoTranscriptFound(CouldNotRetrieveTranscript):
    def __init__(self, video_id: str, requested_language_codes: Iterable[str] = (), transcript_data=None):
        self._requested_language_codes = list(requested_language_codes)
        self._transcript_data = transcript_data
        super().__init__(video_id)

    @property
    def cause(self) -> str:
        cause = f"No transcripts were found for any of the requested language codes: {self._requested_language_codes}"
        if self._transcript_data is not None:
            cause += f"\n\n{self._transcript_data}"
        return cause


# ---- errors that come from the service in between ----------------------------------------------

class TranscriptOutError(YouTubeTranscriptApiException):
    """An error answered by the TranscriptOut API. `status` is the HTTP status, `code` the machine
    code from the response envelope (branch on `code`, not on the message)."""

    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None,
                 request_id: Optional[str] = None):
        self.status = status
        self.code = code
        self.request_id = request_id
        suffix = f" (request_id {request_id})" if request_id else ""
        super().__init__(f"{message}{suffix}")


class AuthenticationError(TranscriptOutError):
    """No API key, or the key was rejected. Get one at https://transcriptout.com/dashboard."""


class InsufficientCredits(TranscriptOutError):
    """The account behind the key has no credits left."""


class RateLimited(TranscriptOutError):
    """Too many requests per minute for this key, still refused after the client's own retries."""


class ServiceUnavailable(TranscriptOutError):
    """TranscriptOut could not serve the request right now, still refused after retries. Not charged."""
