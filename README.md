# transcriptout

`youtube-transcript-api` works on your laptop and breaks in production with `RequestBlocked` or `IpBlocked`, because YouTube blocks cloud IP ranges. `transcriptout` keeps the same interface and fetches through [TranscriptOut](https://transcriptout.com/?utm_source=transcriptout-python&utm_medium=readme), so there are no proxies to run and nothing to block on your side.

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
```

## API key

Sign in at [transcriptout.com](https://transcriptout.com/?utm_source=transcriptout-python&utm_medium=readme) and create a key on the [Keys](https://transcriptout.com/keys?utm_source=transcriptout-python&utm_medium=readme) page. It starts with `sk_`. New accounts start with free credits, no card.

The package reads the key from the `TRANSCRIPTOUT_API_KEY` environment variable, so your code stays the same as with youtube-transcript-api. Set it in the terminal you run your code from.

```bash
# macOS and Linux
export TRANSCRIPTOUT_API_KEY=sk_your_key

# Windows PowerShell
$env:TRANSCRIPTOUT_API_KEY="sk_your_key"
```

That lasts until the terminal is closed. For a project, put the line `TRANSCRIPTOUT_API_KEY=sk_your_key` in a `.env` file and load it with `python-dotenv` (`from dotenv import load_dotenv; load_dotenv()`) before creating the client. On a server, add the variable in your host's settings (Render, Fly, Docker and so on).

Or pass the key in code.

```python
ytt_api = YouTubeTranscriptApi(api_key="sk_your_key")
```

Keep the key out of git. An error saying `No API key` means the variable is not set in the process that runs your code.

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

## Reference

Everything the package exports, in one place.

### `YouTubeTranscriptApi(api_key=None, *, timeout=60.0, max_retries=3, segment=None)`

The client. Every argument is optional.

| Argument | Default | What it does |
| --- | --- | --- |
| `api_key` | `TRANSCRIPTOUT_API_KEY` | Your `sk_` key |
| `timeout` | `60.0` | Seconds per HTTP request |
| `max_retries` | `3` | Retries on 429 and 503, honouring `Retry-After`. Those are not charged |
| `segment` | `None` (180) | Maximum characters per snippet for auto-generated tracks, 20 to 5000. Manual tracks keep the author's lines unless this is set |
| `http_client` | `None` | A `requests.Session` to send requests with |
| `proxy_config` | `None` | Accepted for compatibility and ignored |

### Methods

| Method | Returns | What it does | Cost |
| --- | --- | --- | --- |
| `fetch(video_id, languages=["en"])` | `FetchedTranscript` | The transcript in the first of `languages` the video has. Manual tracks come before auto-generated ones | 1 credit. A missing first language takes extra calls to list the tracks and fetch the next one |
| `list(video_id)` | `TranscriptList` | Every track the video has | 1 credit |
| `fetch_many(video_ids, language="en", *, kind=None, poll_interval=3.0, timeout=None, on_progress=None)` | `BatchResult` | Many videos through one batch job, up to 4,000 per job. Longer lists run as several jobs. `kind` is `"manual"` or `"auto"`. `on_progress` gets the job status after every poll | 1 credit per video |
| `YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])` | `list[dict]` | The pre-1.0 static call. A list of `{text, start, duration}` | as `fetch` |
| `YouTubeTranscriptApi.get_transcripts(video_ids, languages=["en"], continue_after_error=False)` | `(dict, list)` | The pre-1.0 call for many videos, now one batch job instead of a loop. Returns transcripts by id and the ids that failed | 1 credit per video |
| `YouTubeTranscriptApi.list_transcripts(video_id)` | `TranscriptList` | The pre-1.0 name for `list` | 1 credit |

A video id or a full YouTube URL works everywhere a `video_id` is asked for.

### What comes back

| Object | Fields and methods |
| --- | --- |
| `FetchedTranscript` | `snippets`, `video_id`, `language`, `language_code`, `is_generated`, `to_raw_data()`. Iterable, indexable, has `len()` |
| `FetchedTranscriptSnippet` | `text`, `start` and `duration` in seconds |
| `TranscriptList` | Iterable over `Transcript`. `find_transcript(codes)`, `find_manually_created_transcript(codes)`, `find_generated_transcript(codes)` |
| `Transcript` | `video_id`, `language`, `language_code`, `is_generated`, `fetch()` |
| `BatchResult` | `transcripts` (id to `FetchedTranscript`), `errors` (id to exception), `job_ids` |

### Formatters

```python
from transcriptout.formatters import SRTFormatter

srt = SRTFormatter().format_transcript(transcript)
```

`TextFormatter`, `JSONFormatter`, `SRTFormatter`, `WebVTTFormatter` and `PrettyPrintFormatter`, each with `format_transcript(t)` and `format_transcripts([t, ...])`. `FormatterLoader().load("srt")` picks one by name.

### Errors

The youtube-transcript-api exceptions keep their names, so existing `except` blocks work. The ones you will see are `NoTranscriptFound` (no track in that language), `TranscriptsDisabled` (no subtitles at all), `VideoUnavailable`, `AgeRestricted`, `InvalidVideoId`, `YouTubeRequestFailed` and `NotTranslatable`, all subclasses of `CouldNotRetrieveTranscript`.

Errors from the service itself subclass `TranscriptOutError`, which carries `status`, `code` and `request_id`.

| Exception | When |
| --- | --- |
| `AuthenticationError` | No key, or the key was rejected |
| `InsufficientCredits` | The account has no credits left |
| `RateLimited` | Too many requests per minute, still refused after retries |
| `ServiceUnavailable` | Temporary refusal on our side after retries. Not charged |

## What differs

- Auto-generated tracks come grouped into readable segments of up to 180 characters rather than YouTube's short caption lines. Pass `segment=` to the constructor to change the size.
- Translation (`transcript.translate(...)`) is not supported yet and raises `NotTranslatable`.
- `proxy_config` and cookies are accepted and ignored, there is nothing to proxy.
- Video URLs are accepted as well as ids.

## Pricing

One credit per transcript. `fetch` with a language the video lacks costs one more call to list its tracks. Requests refused for reasons on our side are refunded. See [pricing](https://transcriptout.com/?utm_source=transcriptout-python&utm_medium=readme#pricing).

## License

MIT
