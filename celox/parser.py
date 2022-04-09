from typing import Optional, Tuple, Union


class ReceiveBuffer:

    __slots__: Tuple[str, str, str, str] = (
        "_buf",
        "terminator",
        "idx",
        "max_frame_length",
    )

    def __init__(
        self,
        byteslike: Optional[Union[bytes, bytearray]] = None,
        terminator: bytes = b"\r\n\r\n",
        max_frame_length=65535,
    ) -> None:
        self._buf = bytearray()
        if byteslike:
            self._buf += byteslike
        self.terminator = terminator
        self.max_frame_length = max_frame_length
        self.idx = 0

    def read(self) -> Union[bytearray, None]:
        # Find is the next position of terminator in _buf, starting searching from idx.
        terminator_idx = self._buf.find(self.terminator, self.idx)
        # Did we find the terminator in _buf?
        if terminator_idx < 0:
            # No, can we keep looking?
            if len(self._buf) > self.max_frame_length:
                # No, we've reached the size of _buf.
                raise ValueError("frame too long")
            # Yes, set the index to the position where this one ended.
            self.idx = max(0, len(self._buf) - len(self.terminator) + 1)
            # Return that we have not found our terminator yet.
            # Perhaps we could also accept a read_fn parameter which is called until the terminator is found in the buffer.
            # We would also have to check for eof on the read_fn function.
            return None
        # Yes, extract the data by stripping the terminator.
        data = self._buf[:terminator_idx]
        # Delete what we have already searched through, there might still be bytes left after the terminator.
        del self._buf[: terminator_idx + len(self.terminator)]
        # Set the search index to the beginning again.
        self.idx = 0
        return data

    def close(self):
        del self._buf[:]

    def __iadd__(self, byteslike: Union[bytes, bytearray]) -> "ReceiveBuffer":
        self._buf += byteslike
        return self

    def __bool__(self) -> bool:
        return bool(len(self))

    def __len__(self) -> int:
        return len(self._buf)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} idx={self.idx} terminator={self.terminator!r} max_frame_length={self.max_frame_length}>"
