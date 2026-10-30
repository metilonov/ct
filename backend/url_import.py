"""Pinned public IP HTTPS download. No redirects, credentials, local destinations, or unbounded body."""

import socket, ipaddress
from urllib.parse import urlsplit
import httpx


def fetch_torrent(url):
    u = urlsplit(url)
    if (
        u.scheme != "https"
        or not u.hostname
        or u.username
        or u.password
        or u.port not in (None, 443)
    ):
        raise ValueError("https_only")
    addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
    ips = {a[4][0] for a in addresses}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("non_public_address")
    ip = sorted(ips)[0]
    host = "[" + ip + "]" if ":" in ip else ip
    pinned = "https://" + host + (u.path or "/") + ("?" + u.query if u.query else "")
    with httpx.Client(timeout=30, follow_redirects=False) as c:
        with c.stream(
            "GET",
            pinned,
            headers={"Host": u.hostname},
            extensions={"sni_hostname": u.hostname.encode()},
        ) as r:
            r.raise_for_status()
            if r.status_code != 200:
                raise ValueError("redirect_not_allowed")
            body = bytearray()
            for chunk in r.iter_bytes(64 * 1024):
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("torrent_too_large")
            return bytes(body)
