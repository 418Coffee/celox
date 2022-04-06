import yarl
from multidict import CIMultiDict

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")

def make_request(method: str, url: yarl.URL, headers: CIMultiDict[str, str], body: str) -> bytes:
    request = bytes()
    request += crlf(f"{method} {url.raw_path_qs} HTTP/1.1")
    for k, v in headers.items():
        request += crlf(f"{k}: {v}")
    request += crlf("")
    if body is not None:
        request += body.encode("ascii")
    return request
    
def crlf(s: str) -> bytes:
    return f"{s}\r\n".encode("ascii")
