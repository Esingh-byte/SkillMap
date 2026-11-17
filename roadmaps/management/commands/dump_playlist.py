r"""
Management command: dump_playlist

Fetches playlist metadata and video details from YouTube Data API v3 using only
the Python standard library and writes a normalized JSON file for offline import.

Usage:
    .\.venv\Scripts\python.exe manage.py dump_playlist <playlist_id_or_url> --out data/playlists/<name>.json
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

_ISO8601_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)

_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,128}$")


def scrub_api_key(text: str, api_key: str = "") -> str:
    """Remove any YouTube API key from URLs or error strings."""
    if not text:
        return ""
    scrubbed = re.sub(r"([?&]key=)[^&\s\"']+", r"\1[REDACTED]", str(text))
    if api_key:
        scrubbed = scrubbed.replace(api_key, "[REDACTED]")
    return scrubbed


def parse_iso8601_duration(duration_str: str) -> int:
    """
    Parse an ISO 8601 duration string (e.g. 'PT1H2M3S', 'PT45S', 'P0D')
    into total seconds. Raises ValueError on invalid input.
    """
    if not isinstance(duration_str, str) or not duration_str:
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str!r}")
    if duration_str in ("P", "PT") or duration_str.endswith("T"):
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str!r}")

    match = _ISO8601_DURATION_RE.match(duration_str)
    if not match:
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str!r}")

    parts = match.groupdict()
    if all(v is None for v in parts.values()):
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str!r}")

    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def extract_playlist_id(playlist_id_or_url: str) -> str:
    """
    Extract a playlist ID from either a bare playlist ID or a URL containing 'list='.
    Raises CommandError if the input is not a valid playlist ID or URL.
    """
    raw = (playlist_id_or_url or "").strip()
    if not raw:
        raise CommandError("Playlist ID or URL cannot be empty.")

    if "://" in raw or "?" in raw or "/" in raw or "list=" in raw:
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
        query = urllib.parse.parse_qs(parsed.query)
        if not query.get("list") and "list=" in raw:
            # Handle bare query-like string such as 'list=PL123'
            query = urllib.parse.parse_qs(raw.split("?", 1)[-1])
        list_vals = query.get("list", [])
        if not list_vals or not list_vals[0].strip():
            raise CommandError(
                "Could not find a 'list=' parameter in the provided playlist URL."
            )
        candidate = list_vals[0].strip()
    else:
        candidate = raw

    if not _PLAYLIST_ID_RE.match(candidate):
        raise CommandError(f"Invalid playlist ID: '{candidate}'.")

    return candidate


def fetch_json(url: str) -> dict:
    """
    Perform an HTTP GET request and parse the response body as JSON.
    Kept as a single small function so unit tests can patch it directly.
    """
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_youtube_api(url: str, api_key: str) -> dict:
    """Call fetch_json(url) and translate HTTP/network errors with key scrubbing."""
    try:
        return fetch_json(url)
    except urllib.error.HTTPError as exc:
        code = exc.code
        if code in (400, 403):
            raise CommandError(
                f"YouTube API error (HTTP {code}): quota exceeded, invalid API key, "
                "or invalid request parameter."
            ) from None
        if code == 404:
            raise CommandError(
                "Playlist not found (HTTP 404): check the playlist ID and ensure it is public."
            ) from None
        safe_msg = scrub_api_key(str(exc), api_key)
        raise CommandError(f"YouTube API HTTP error ({code}): {safe_msg}") from None
    except urllib.error.URLError as exc:
        safe_msg = scrub_api_key(str(exc.reason), api_key)
        raise CommandError(f"Network error contacting YouTube API: {safe_msg}") from None
    except CommandError:
        raise
    except Exception as exc:
        safe_msg = scrub_api_key(str(exc), api_key)
        raise CommandError(f"Failed to fetch data from YouTube API: {safe_msg}") from None


def _is_private_or_deleted_item(item: dict) -> str | None:
    """Return a skip reason if a playlistItem represents a private or deleted video."""
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    title = (snippet.get("title") or "").strip()
    privacy = (status.get("privacyStatus") or "").strip().lower()

    if privacy == "private" or title.lower() == "private video":
        return "private video"
    if title.lower() == "deleted video":
        return "deleted video"

    content_details = item.get("contentDetails") or {}
    resource_id = snippet.get("resourceId") or {}
    video_id = content_details.get("videoId") or resource_id.get("videoId")
    if not video_id or not snippet:
        return "missing video data"
    return None


class Command(BaseCommand):
    help = "Dump a YouTube playlist to a JSON file using YouTube Data API v3."

    def add_arguments(self, parser):
        parser.add_argument(
            "playlist",
            help="YouTube playlist ID or full URL containing list=<playlist_id>.",
        )
        parser.add_argument(
            "--out",
            required=True,
            help="Output JSON file path (e.g. data/playlists/python.json).",
        )

    def handle(self, *args, **options):
        api_key = (getattr(settings, "YOUTUBE_API_KEY", "") or "").strip()
        if not api_key:
            raise CommandError(
                "YOUTUBE_API_KEY is not set. Configure YOUTUBE_API_KEY in your environment or .env file."
            )

        playlist_id = extract_playlist_id(options["playlist"])
        out_path = Path(options["out"])

        # 1. Fetch all playlistItems pages (maxResults=50)
        raw_items: list[dict] = []
        page_token: str | None = None
        playlist_title = ""
        playlist_channel = ""

        while True:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": "50",
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            url = f"{YOUTUBE_API_BASE}/playlistItems?{urllib.parse.urlencode(params)}"
            payload = _call_youtube_api(url, api_key)

            if not playlist_title and payload.get("title"):
                playlist_title = str(payload["title"])
            if not playlist_channel and payload.get("channel"):
                playlist_channel = str(payload["channel"])

            page_items = payload.get("items") or []
            raw_items.extend(page_items)

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        if not raw_items:
            raise CommandError(
                f"Playlist '{playlist_id}' returned no items or was not found."
            )

        # Determine whether snippet.position is 0-based (standard YouTube API) or 1-based
        first_raw_pos = (raw_items[0].get("snippet") or {}).get("position")
        zero_based = first_raw_pos == 0

        candidate_entries: list[dict] = []
        skipped: list[tuple[int, str, str]] = []

        for idx, item in enumerate(raw_items, start=1):
            snippet = item.get("snippet") or {}
            content_details = item.get("contentDetails") or {}
            resource_id = snippet.get("resourceId") or {}
            raw_pos = snippet.get("position")
            if isinstance(raw_pos, int):
                position = raw_pos + 1 if zero_based else raw_pos
            else:
                position = idx

            if not playlist_title and snippet.get("playlistTitle"):
                playlist_title = str(snippet["playlistTitle"])
            if not playlist_channel and snippet.get("channelTitle"):
                playlist_channel = str(snippet["channelTitle"])

            video_id = content_details.get("videoId") or resource_id.get("videoId") or ""
            reason = _is_private_or_deleted_item(item)
            if reason is not None:
                skipped.append((position, video_id or "unknown", reason))
                continue

            candidate_entries.append(
                {
                    "position": position,
                    "video_id": video_id,
                    "fallback_title": snippet.get("title") or "",
                    "fallback_channel": (
                        snippet.get("videoOwnerChannelTitle")
                        or snippet.get("channelTitle")
                        or ""
                    ),
                }
            )

        # 2. Fetch videos.list in chunks of 50 IDs
        video_details_by_id: dict[str, dict] = {}
        video_ids = [entry["video_id"] for entry in candidate_entries]
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            params = {
                "part": "contentDetails,status,snippet",
                "id": ",".join(chunk),
                "key": api_key,
            }
            url = f"{YOUTUBE_API_BASE}/videos?{urllib.parse.urlencode(params)}"
            payload = _call_youtube_api(url, api_key)
            for v_item in payload.get("items") or []:
                vid = v_item.get("id")
                if vid:
                    video_details_by_id[vid] = v_item

        videos_out: list[dict] = []
        for entry in candidate_entries:
            pos = entry["position"]
            vid = entry["video_id"]
            v_item = video_details_by_id.get(vid)
            if not v_item:
                skipped.append((pos, vid, "no data returned by videos.list (private/deleted)"))
                continue

            v_snippet = v_item.get("snippet") or {}
            v_content = v_item.get("contentDetails") or {}
            v_status = v_item.get("status") or {}

            privacy = (v_status.get("privacyStatus") or "").strip().lower()
            raw_duration = v_content.get("duration")
            if privacy == "private" or not raw_duration:
                skipped.append((pos, vid, "private or missing duration"))
                continue

            duration_seconds = parse_iso8601_duration(raw_duration)
            embeddable = bool(v_status.get("embeddable", True))
            title = v_snippet.get("title") or entry["fallback_title"]
            channel = (
                v_snippet.get("channelTitle")
                or entry["fallback_channel"]
                or playlist_channel
            )

            if not playlist_channel and channel:
                playlist_channel = channel

            videos_out.append(
                {
                    "position": pos,
                    "video_id": vid,
                    "title": title,
                    "channel": channel,
                    "duration_seconds": duration_seconds,
                    "embeddable": embeddable,
                }
            )

        if not playlist_title:
            playlist_title = f"Playlist {playlist_id}"

        output_data = {
            "playlist_id": playlist_id,
            "title": playlist_title,
            "channel": playlist_channel,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "videos": videos_out,
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(output_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Print summary
        total_kept = len(videos_out)
        embeddable_count = sum(1 for v in videos_out if v["embeddable"])
        non_embeddable_count = total_kept - embeddable_count
        skipped_count = len(skipped)
        total_seconds = sum(v["duration_seconds"] for v in videos_out)
        total_hours = total_seconds / 3600.0

        self.stdout.write(f"Saved playlist dump to {out_path}")
        if skipped:
            self.stdout.write("Skipped videos:")
            for pos, vid, reason in skipped:
                self.stdout.write(f"  - position {pos} ({vid}): {reason}")

        self.stdout.write(
            f"Summary: total={total_kept}, embeddable={embeddable_count}, "
            f"non_embeddable={non_embeddable_count}, skipped={skipped_count}, "
            f"duration={total_hours:.2f} hours"
        )
