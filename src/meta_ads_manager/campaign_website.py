"""Bounded public HTTPS retrieval. Pins a validated public IP; no cookies or forms."""

import hashlib
import http.client
import ipaddress
import socket
import ssl
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from meta_ads_manager.decision_store import fail


def public_target(url):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
        or any(c.isspace() for c in url)
    ):
        fail("WEBSITE_URL", "Podaj publiczny adres HTTPS bez danych logowania.")
    addresses = {r[4][0] for r in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        fail("WEBSITE_URL", "Adres lokalny lub prywatny jest niedozwolony.")
    return p, sorted(addresses)[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=15, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        self.sock = self._context.wrap_socket(
            socket.create_connection((self.ip, 443), self.timeout), server_hostname=self.host
        )


def fetch(url):
    for _ in range(4):
        p, ip = public_target(url)
        connection = PinnedHTTPS(p.hostname, ip)
        try:
            connection.request(
                "GET",
                urlunsplit(("", "", p.path or "/", p.query, "")),
                headers={"User-Agent": "MetaAdsWorkbench/0.4", "Accept": "text/html"},
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    fail("WEBSITE_RESPONSE", "Brak celu przekierowania.")
                url = urljoin(url, location)
                continue
            if response.status != 200 or "text/html" not in response.getheader("Content-Type", ""):
                fail("WEBSITE_RESPONSE", "Strona nie zwróciła dokumentu HTML.")
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                fail("WEBSITE_SIZE", "Strona przekracza limit 1 MB.")
            charset = response.headers.get_content_charset() or "utf-8"
            return url, body.decode(charset, errors="replace")
        finally:
            connection.close()
    fail("WEBSITE_REDIRECT", "Zbyt wiele przekierowań.")


class Extractor(HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.url, self.skip, self.title_depth = url, 0, 0
        self.text, self.title, self.links, self.images, self.description = [], [], [], [], ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "title":
            self.title_depth += 1
        if self.skip:
            return
        if tag == "meta" and a.get("name", "").lower() == "description":
            self.description = a.get("content", "")[:2000]
        if tag == "a" and a.get("href"):
            link = urljoin(self.url, a["href"])
            if urlsplit(link).scheme == "https":
                self.links.append(link)
        if tag == "img" and a.get("src"):
            self.images.append(urljoin(self.url, a["src"]))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())
            if self.title_depth:
                self.title.append(data.strip())


def collect(url):
    final_url, html = fetch(url)
    p = Extractor(final_url)
    p.feed(html)
    return {
        "url": final_url,
        "requested_url": url,
        "fetched_at": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "title": " ".join(p.title)[:1000],
        "description": p.description,
        "text": "\n".join(p.text)[:30000],
        "links": list(dict.fromkeys(p.links))[:100],
        "images": list(dict.fromkeys(p.images))[:30],
        "trust": "untrusted_public_content",
        "operator_confirmed": False,
    }
