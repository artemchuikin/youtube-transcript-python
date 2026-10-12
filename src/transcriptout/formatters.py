"""Formatters with the names and call shape of youtube_transcript_api.formatters."""
import json
from typing import List

from ._transcripts import FetchedTranscript


class Formatter:
    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        raise NotImplementedError

    def format_transcripts(self, transcripts: List[FetchedTranscript], **kwargs) -> str:
        raise NotImplementedError


class PrettyPrintFormatter(Formatter):
    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        import pprint
        return pprint.pformat(transcript.to_raw_data(), **kwargs)

    def format_transcripts(self, transcripts: List[FetchedTranscript], **kwargs) -> str:
        import pprint
        return pprint.pformat([t.to_raw_data() for t in transcripts], **kwargs)


class JSONFormatter(Formatter):
    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        return json.dumps(transcript.to_raw_data(), **kwargs)

    def format_transcripts(self, transcripts: List[FetchedTranscript], **kwargs) -> str:
        return json.dumps([t.to_raw_data() for t in transcripts], **kwargs)


class TextFormatter(Formatter):
    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        return "\n".join(s.text for s in transcript)

    def format_transcripts(self, transcripts: List[FetchedTranscript], **kwargs) -> str:
        return "\n\n\n".join(self.format_transcript(t, **kwargs) for t in transcripts)


class _Timed(TextFormatter):
    _sep = ","

    def _stamp(self, seconds: float) -> str:
        ms = int(round(max(seconds, 0.0) * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}{self._sep}{ms:03d}"

    def _cues(self, transcript: FetchedTranscript):
        snippets = list(transcript)
        for i, s in enumerate(snippets):
            end = s.start + s.duration
            if i + 1 < len(snippets) and snippets[i + 1].start < end:
                end = snippets[i + 1].start
            yield i, f"{self._stamp(s.start)} --> {self._stamp(end)}", s.text


class SRTFormatter(_Timed):
    _sep = ","

    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        return "\n\n".join(f"{i + 1}\n{span}\n{text}" for i, span, text in self._cues(transcript)) + "\n"


class WebVTTFormatter(_Timed):
    _sep = "."

    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        return "WEBVTT\n\n" + "\n\n".join(f"{span}\n{text}" for _, span, text in self._cues(transcript)) + "\n"


class FormatterLoader:
    TYPES = {
        "json": JSONFormatter,
        "pretty": PrettyPrintFormatter,
        "text": TextFormatter,
        "webvtt": WebVTTFormatter,
        "srt": SRTFormatter,
    }

    def load(self, formatter_type: str = "pretty") -> Formatter:
        if formatter_type not in self.TYPES:
            raise ValueError(f"Unknown formatter {formatter_type!r}, choose one of {sorted(self.TYPES)}")
        return self.TYPES[formatter_type]()
