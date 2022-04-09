import pytest
from celox import InvalidProxy
from celox.proxy import _prepare_proxy, _connect_request


def test_connect_request():
    req = _connect_request("localhost", 8888)
    assert b"Proxy-Authorization: basic" not in req


def test_connect_request_user_pass():
    req = _connect_request("localhost", 8888, user="hello", password="test")
    assert b"Proxy-Authorization: basic" in req


def test_prepare_proxy_invalid():
    invalid = "bad://"
    with pytest.raises(InvalidProxy):
        _prepare_proxy(invalid)


def test_prepare_proxy_invalid_none():
    invalid = None
    with pytest.raises(InvalidProxy):
        _prepare_proxy(invalid)
