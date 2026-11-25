"""Configuration regressions for Nginx's internal request handling."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_internal_routes_are_only_reachable_by_internal_subrequests():
    config = (ROOT / 'core/nginx/conf/nginx.conf').read_text()
    location = re.search(
        r'location\s+\^~\s+/internal\s*\{(.*?)\n\s*\}',
        config,
        re.DOTALL,
    )

    assert location is not None
    assert re.search(r'\binternal\s*;', location.group(1))
