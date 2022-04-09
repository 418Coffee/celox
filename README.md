# celox

![Tests](https://github.com/418Coffee/celox/actions/workflows/tests.yaml/badge.svg)
[![Coverage Status](https://coveralls.io/repos/github/418Coffee/celox/badge.svg?branch=main&service=github)](https://coveralls.io/github/418Coffee/celox?branch=main&service=github)

Minimalistic, fast HTTP/1.1 client using [trio](https://github.com/python-trio/trio) as a backend.

Syntax is similair to [aiohttp](https://github.com/aio-libs/aiohttp) and [requests](https://github.com/psf/requests).

## Features

- [x] GET, HEAD, POST, PUT, PATCH, DELETE methods
- [x] HTTP & HTTPS proxies
- [x] Timeouts
- [x] Cookie handling
- [x] Aiohttp-esque response body streaming.
- [x] Disable SSL/TLS verification
- [x] Connection caching

## Table of contents

- [Quickstart](#quickstart)
- [API Overview](#api-overview)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)

## Quickstart

1. Install celox

```cmd
pip install celox
```

2. Have fun 🥳

```python
import trio
import celox


async def main():
    async with celox.Client() as client:
        async with client.get("https://httpbin.org/") as resp:
            body = await resp.read()
            print(body)
            print(resp)

trio.run(main)
```

3. For more examples take a look [here](https://github.com/418Coffee/celox/tree/main/examples)

## API Overview

**TODO**

## Dependencies

- [trio](https://github.com/python-trio/trio)
- [multidict](https://github.com/aio-libs/multidict)
- [yarl](https://github.com/aio-libs/yarl)
- [attrs](https://github.com/python-attrs/attrs)

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
