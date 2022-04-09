import ssl
import pytest
import yarl

from celox.util import (
    FrozenOrderedDict,
    create_ssl_context,
    frozendict,
    is_ip_address,
    is_ssl,
    reify,
    winsock2strerror,
)


@pytest.mark.parametrize(
    "frozen", [frozendict({"a": "b"}), FrozenOrderedDict({"a": "b"})]
)
def test_frozendict(frozen):
    with pytest.raises(TypeError):
        frozen["c"] = "d"


@pytest.mark.parametrize(
    "url,expected",
    [
        (yarl.URL("http://"), False),
        (yarl.URL("https://"), True),
        (yarl.URL("http://localhost:443"), True),
        (yarl.URL("https://localhost:80"), True),
        (yarl.URL("ftp://localhost:80"), False),
    ],
)
def test_is_ssl(url, expected):
    assert is_ssl(url) == expected


@pytest.mark.parametrize(
    "ctx,check_hostname,verify_mode",
    [
        (create_ssl_context(ssl_skip_verify=False), True, ssl.CERT_REQUIRED),
        (create_ssl_context(ssl_skip_verify=True), False, ssl.CERT_NONE),
    ],
)
def test_create_ssl_context(ctx: ssl.SSLContext, check_hostname, verify_mode):
    assert ctx.check_hostname == check_hostname
    assert ctx.verify_mode == verify_mode


@pytest.mark.parametrize(
    "host,expected",
    [
        ("192.168.0.0", True),
        ("www.google.com", False),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", True),
        (None, False),
        (b"10.10.10.10", True),
        (1, False),
    ],
)
def test_is_ip_address(host, expected):
    if isinstance(host, int):
        with pytest.raises(TypeError):
            assert is_ip_address(host) == expected
    else:
        assert is_ip_address(host) == expected


@pytest.mark.parametrize(
    "errcode,expected",
    [
        (10060, "Connection timed out"),
        (10052, "Network dropped connection on reset"),
        (0, "Unknown error"),
    ],
)
def test_winsock2strerror(errcode, expected):
    assert winsock2strerror(errcode) == expected


def test_reify():
    class Test:
        @reify
        def dict(self):
            return {"a": "b"}

    t = Test()
    with pytest.raises(AttributeError):
        t.dict = {}
