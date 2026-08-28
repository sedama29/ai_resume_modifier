"""Overleaf's own officially-supported "Open in Overleaf" link -- the same
mechanism LaTeX template galleries use. It requires no API key and no
authenticated session with this app: Overleaf's server fetches snip_uri
itself and creates a NEW project (in whichever Overleaf account the user is
signed into in their browser, or an anonymous one) seeded with that file's
content.

This is NOT a live-synced/linked project -- there is no persistent Overleaf
project this app writes back to. Every click creates a fresh project. That's
a real constraint of not having an Overleaf API subscription or the user's
Overleaf login, not a placeholder."""
from urllib.parse import urlencode


def build_open_in_overleaf_url(tex_signed_url: str, filename: str = "main.tex") -> str:
    query = urlencode({"snip_uri": tex_signed_url, "snip_name": filename})
    return f"https://www.overleaf.com/docs?{query}"
