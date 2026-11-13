from cyguide.common.canonicalize import canonicalize_host, canonicalize_port, canonicalize_url


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


def test_canonicalize_field():
    from cyguide.common.canonicalize import canonicalize_field

    assert canonicalize_field("ip", " 192.168.1.1 ") == "192.168.1.1"
    assert canonicalize_field("host_ip", "LOCALHOST") == "127.0.0.1"
    assert canonicalize_field("port", "8080") == 8080
    assert canonicalize_field("protocol", " TCP ") == "tcp"
    assert canonicalize_field("url", "HTTP://EXAMPLE.COM:80/TEST") == "http://example.com/TEST"
    assert canonicalize_field("other", "  spaced  ") == "spaced"
    assert canonicalize_field("none_field", None) is None


def test_canonicalize_mapping():
    from cyguide.common.canonicalize import canonicalize_mapping

    raw = {
        "ip": " 10.0.0.1 ",
        "port": "443",
        "protocol": "TCP",
        "nested": {"url": "HTTP://FOO.COM:80/BAR"},
        "tags": [" ONE ", " TWO "],
    }
    normalized = canonicalize_mapping(raw)
    assert normalized == {
        "ip": "10.0.0.1",
        "port": 443,
        "protocol": "tcp",
        "nested": {"url": "http://foo.com/BAR"},
        "tags": ["ONE", "TWO"],
    }
