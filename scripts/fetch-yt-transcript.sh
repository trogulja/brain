#!/usr/bin/env bash
# Fetch a YouTube video's transcript as plain text.
#
# Usage: fetch-yt-transcript.sh <youtube-url>
#
# Prefers manually-uploaded English subs, falls back to auto-generated.
# Prints a metadata header followed by the deduped transcript on stdout.
# Exits non-zero with a stderr message if no subtitles are available.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $(basename "$0") <youtube-url>" >&2
  exit 2
fi

url="$1"

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "error: yt-dlp not found on PATH (brew install yt-dlp)" >&2
  exit 1
fi

case "$url" in
  *youtube.com/*|*youtu.be/*) ;;
  *)
    echo "error: not a YouTube URL: $url" >&2
    exit 2
    ;;
esac

tmpdir=$(mktemp -d -t yt-transcript)
trap 'rm -rf "$tmpdir"' EXIT

meta=$(yt-dlp --skip-download --no-warnings \
  --print "title:%(title)s" \
  --print "uploader:%(uploader)s" \
  --print "duration:%(duration_string)s" \
  --print "id:%(id)s" \
  "$url" 2>/dev/null) || {
    echo "error: yt-dlp failed to fetch metadata for $url" >&2
    exit 1
  }

yt-dlp --skip-download --write-sub --write-auto-sub \
  --sub-lang "en.*" --sub-format vtt --no-warnings \
  -o "$tmpdir/%(id)s.%(ext)s" \
  "$url" >/dev/null 2>&1 || {
    echo "error: yt-dlp failed to fetch subtitles for $url" >&2
    exit 1
  }

vtt=$(find "$tmpdir" -name '*.vtt' -print -quit)
if [[ -z "$vtt" ]]; then
  echo "error: no subtitles available for $url" >&2
  exit 1
fi

echo "URL: $url"
echo "$meta" | sed 's/^/# /'
echo

awk '
  /^WEBVTT/ || /^NOTE/ || /^Kind:/ || /^Language:/ { next }
  /-->/ { next }
  /^[[:space:]]*$/ { next }
  {
    gsub(/<[^>]*>/, "")
    gsub(/&nbsp;/, " ")
    gsub(/&amp;/, "\\&")
    gsub(/&lt;/, "<")
    gsub(/&gt;/, ">")
    print
  }
' "$vtt" | awk '!seen[$0]++'
