import pytest
from cyguide.engine.canonicalize import canonicalize_host, canonicalize_port, canonicalize_url

def test_canonicalize_host():
    assert canonicalize_host(" 127.0.0.1 ") == "127.0.0.1"
    assert canonicalize_host("GOOGLE.COM") == "google.com"

def test_canonicalize_port():
    assert canonicalize_port(80) == 80
    assert canonicalize_port("80") == 80

def test_canonicalize_url():
    assert canonicalize_url("HTTP://example.com:80/PATH/") == "http://example.com/PATH/"
    assert canonicalize_url("https://example.com") == "https://example.com"
    assert canonicalize_url("HTTP://example.com:443/api") == "http://example.com:443/api"
