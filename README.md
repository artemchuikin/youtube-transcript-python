# transcriptout

`youtube-transcript-api` works on your laptop and breaks in production with `RequestBlocked` or `IpBlocked`, because YouTube blocks cloud IP ranges. `transcriptout` keeps the same interface and fetches through [TranscriptOut](https://transcriptout.com), so there are no proxies to run and nothing to block on your side.

Migration is one line.

```python
# from youtube_transcript_api import YouTubeTranscriptApi
from transcriptout import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()   # reads TRANSCRIPTOUT_API_KEY
transcript = ytt_api.fetch("dQw4w9WgXcQ", languages=["de", "en"])

for snippet in transcript:
    print(snippet.start, snippet.text)
```

## Install

```bash
pip install transcriptout
export TRANSCRIPTOUT_API_KEY=sk_...
```

Get a free key at [transcriptout.com](https://transcriptout.com). New accounts start with free credits, no card.

## What stays the same

- `fetch(video_id, languages=...)`, `list(video_id)`, `find_transcript`, `find_manually_created_transcript`, `find_generated_transcript`
- `FetchedTranscript` and `FetchedTranscriptSnippet` with `.text`, `.start`, `.duration`, `.to_raw_data()`
- Exception names, so `except NoTranscriptFound:` keeps working
- Formatters in `transcriptout.formatters` (`TextFormatter`, `JSONFormatter`, `SRTFormatter`, `WebVTTFormatter`)
- The static `get_transcript`, `get_transcripts` and `list_transcripts`, removed from youtube-transcript-api in 1.2.0, work again

## What is new

Many videos in one call, up to 4,000 per job, with retries handled on our side.

```python
result = ytt_api.fetch_many(video_ids, language="en")
for video_id, transcript in result.transcripts.items():
    ...
for video_id, error in result.errors.items():
    ...
```

## What differs

- Auto-generated tracks come grouped into readable segments of up to 180 characters rather than YouTube's short caption lines. Pass `segment=` to the constructor to change the size.
- Translation (`transcript.translate(...)`) is not supported yet and raises `NotTranslatable`.
- `proxy_config` and cookies are accepted and ignored, there is nothing to proxy.
- Video URLs are accepted as well as ids.

## Pricing

One credit per transcript. `fetch` with a language the video lacks costs one more call to list its tracks. Requests refused for reasons on our side are refunded. See [pricing](https://transcriptout.com/#pricing).

## License

MIT
