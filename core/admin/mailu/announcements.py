"""Sanitized announcement drafts and one-use broadcast confirmations."""
import json
import secrets
import time
from urllib.parse import urlsplit
from html.parser import HTMLParser
import nh3
import flask

TAGS = {'p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'ol', 'ul', 'li', 'a', 'blockquote'}

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'br', 'h1', 'h2', 'h3', 'blockquote', 'li'}:
            self.parts.append('\n' + ('• ' if tag == 'li' else ''))
        if tag == 'a':
            self.link = dict(attrs).get('href')

    def handle_endtag(self, tag):
        if tag == 'a' and self.link:
            self.parts.append(' <' + self.link + '>')
            self.link = None
        if tag in {'p', 'li', 'h1', 'h2', 'h3', 'blockquote'}:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)

def sanitize(value):
    html = nh3.clean(value, tags=TAGS, attributes={'a': {'href', 'title'}},
                     url_schemes={'http', 'https', 'mailto'},
                     attribute_filter=lambda tag, attr, value: value if attr != 'href' or urlsplit(value).scheme in {'http', 'https', 'mailto'} else None,
                     clean_content_tags={'script', 'style', 'iframe', 'object'})
    parser = PlainText()
    parser.feed(html)
    plain = '\n'.join(line.rstrip() for line in ''.join(parser.parts).splitlines()).strip()
    if not plain:
        raise ValueError('Enter a message before continuing.')
    return html, plain

def save(subject, html, plain, recipients, owner):
    token = secrets.token_urlsafe(32)
    draft = dict(subject=subject, html=html, plain=plain, recipients=recipients,
                 owner=owner, expires=time.time() + 1800)
    flask.current_app.session_store.put(('token-announcement-' + token).encode(), json.dumps(draft).encode(), ttl=1800)
    return token, draft

def load(token, owner, consume=False):
    if not isinstance(token, str) or len(token) > 64:
        return None
    store = flask.current_app.session_store
    key = ('token-announcement-' + token).encode()
    try:
        raw = store.get(key)
    except KeyError:
        return None
    draft = json.loads(raw)
    if draft['owner'] != owner or draft['expires'] <= time.time():
        return None
    if consume:
        # GETDEL is atomic across workers; dict.pop provides the in-memory test equivalent.
        raw = store.redis.getdel(key) if hasattr(store, 'redis') else store.dict.pop(key, None)
        if raw is None:
            return None
    return draft
