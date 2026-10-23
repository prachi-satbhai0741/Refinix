"""A minimal RESP2 client, standard library only.

`redis-py` would be the obvious dependency, and it is deliberately not added.
The worker image pins every wheel by hash in `backend/worker-image/requirements.lock`,
so a new runtime dependency means a new lock entry, new provenance, and a new
image build — for a protocol whose client half is a length-prefixed encoder and
a five-case parser. AF-005 needs `XADD`, `XREADGROUP`, `XACK`, `XAUTOCLAIM` and
a handful of key commands; that is what this speaks, and nothing else.

What it deliberately does not do: pipelining, pub/sub, cluster redirection,
RESP3, connection pooling, or automatic reconnection with retried writes. A
dropped connection surfaces as `RedisUnavailable` and the caller decides — an
automatic retry of a non-idempotent `XADD` would duplicate dispatch entries,
which is precisely the failure AF-005 must not have.

Every read is bounded. A reply larger than `MAX_REPLY_BYTES`, or an array longer
than `MAX_ARRAY_ITEMS`, aborts the connection rather than being buffered: this
client talks to an internal Redis, but "internal" is a network position, not a
promise about what arrives on the socket.
"""

from __future__ import annotations

import socket
import threading

MAX_REPLY_BYTES = 8 * 1024 * 1024
MAX_ARRAY_ITEMS = 100_000
MAX_LINE_BYTES = 64 * 1024
CONNECT_TIMEOUT = 5.0
DEFAULT_TIMEOUT = 10.0


class RedisError(Exception):
    """Redis answered, and the answer was an error reply."""


class RedisUnavailable(Exception):
    """The connection failed, timed out, or produced an unparsable reply.

    Distinct from `RedisError` because the two demand different handling: an
    error reply is a bug or a rejected command, an unavailable server is the
    `redis_lost` condition the contract has a failure code for.
    """


class Redis:
    """One connection, one lock. Not a pool.

    A single socket with a mutex is enough for both callers here — the worker
    API enqueues, the executor consumes — and it makes the blocking-read
    behaviour of `XREADGROUP BLOCK` obvious rather than surprising. Give a
    blocking consumer its own instance.
    """

    def __init__(self, host: str, port: int = 6379, *, password: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = int(port)
        self._password = password
        self._timeout = timeout
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._buffer = b""

    # ------------------------------------------------------------ transport ---

    def _connect(self) -> socket.socket:
        try:
            connection = socket.create_connection((self.host, self.port),
                                                  timeout=CONNECT_TIMEOUT)
        except OSError as exc:
            raise RedisUnavailable(f"cannot reach redis at {self.host}:{self.port}") from exc
        connection.settimeout(self._timeout)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket = connection
        self._buffer = b""
        if self._password:
            # Sent on this connection only; never stored beyond this instance
            # and never echoed into an exception message.
            self._raw_command([b"AUTH", self._password.encode("utf-8")])
        return connection

    def close(self) -> None:
        with self._lock:
            self._drop()

    def _drop(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        self._buffer = b""

    @staticmethod
    def _encode(args: list) -> bytes:
        out = [b"*%d\r\n" % len(args)]
        for arg in args:
            if isinstance(arg, bytes):
                raw = arg
            elif isinstance(arg, str):
                raw = arg.encode("utf-8")
            elif isinstance(arg, bool):
                raise TypeError("redis arguments are bytes, str, int or float")
            elif isinstance(arg, (int, float)):
                raw = str(arg).encode("ascii")
            else:
                raise TypeError("redis arguments are bytes, str, int or float")
            out.append(b"$%d\r\n" % len(raw))
            out.append(raw)
            out.append(b"\r\n")
        return b"".join(out)

    def _fill(self) -> None:
        assert self._socket is not None
        try:
            chunk = self._socket.recv(65536)
        except socket.timeout as exc:
            raise RedisUnavailable("redis read timed out") from exc
        except OSError as exc:
            raise RedisUnavailable("redis connection failed") from exc
        if not chunk:
            raise RedisUnavailable("redis closed the connection")
        self._buffer += chunk
        if len(self._buffer) > MAX_REPLY_BYTES:
            raise RedisUnavailable("redis reply exceeded the size limit")

    def _read_line(self) -> bytes:
        while b"\r\n" not in self._buffer:
            if len(self._buffer) > MAX_LINE_BYTES:
                raise RedisUnavailable("redis reply line exceeded the size limit")
            self._fill()
        line, self._buffer = self._buffer.split(b"\r\n", 1)
        return line

    def _read_exactly(self, count: int) -> bytes:
        while len(self._buffer) < count + 2:            # payload plus CRLF
            self._fill()
        data = self._buffer[:count]
        self._buffer = self._buffer[count + 2:]
        return data

    def _read_reply(self, depth: int = 0):
        if depth > 8:
            raise RedisUnavailable("redis reply nested too deeply")
        line = self._read_line()
        if not line:
            raise RedisUnavailable("empty redis reply")
        marker, body = line[:1], line[1:]
        if marker == b"+":
            return body
        if marker == b"-":
            raise RedisError(body.decode("utf-8", "replace")[:256])
        if marker == b":":
            return int(body)
        if marker == b"$":
            length = int(body)
            if length == -1:
                return None
            if length > MAX_REPLY_BYTES:
                raise RedisUnavailable("redis bulk reply exceeded the size limit")
            return self._read_exactly(length)
        if marker == b"*":
            count = int(body)
            if count == -1:
                return None
            if count > MAX_ARRAY_ITEMS:
                raise RedisUnavailable("redis array reply exceeded the item limit")
            return [self._read_reply(depth + 1) for _ in range(count)]
        raise RedisUnavailable("unrecognised redis reply type")

    def _raw_command(self, args: list):
        """Send and read on an already-established socket, without the lock."""
        assert self._socket is not None
        try:
            self._socket.sendall(self._encode(args))
        except OSError as exc:
            raise RedisUnavailable("redis write failed") from exc
        return self._read_reply()

    def command(self, *args, timeout: float | None = None):
        """One request, one reply.

        A `RedisUnavailable` drops the socket so the next call reconnects. A
        `RedisError` does not: the server is healthy and answered, and throwing
        away a working connection on a rejected command would turn a typed
        refusal into a reconnect storm.
        """
        with self._lock:
            if self._socket is None:
                self._connect()
            if timeout is not None:
                self._socket.settimeout(timeout)
            try:
                return self._raw_command(list(args))
            except RedisUnavailable:
                self._drop()
                raise
            finally:
                if timeout is not None and self._socket is not None:
                    try:
                        self._socket.settimeout(self._timeout)
                    except OSError:
                        pass

    # ------------------------------------------------------------- helpers ---

    def ping(self) -> bool:
        try:
            return self.command("PING") in (b"PONG", "PONG")
        except (RedisError, RedisUnavailable):
            return False

    def xadd(self, key: str, fields: dict, *, maxlen: int | None = None) -> str:
        args = ["XADD", key]
        if maxlen is not None:
            args += ["MAXLEN", "~", maxlen]
        args.append("*")
        for name, value in fields.items():
            args += [name, value]
        return _text(self.command(*args))

    def xgroup_create(self, key: str, group: str, *, start: str = "0") -> bool:
        """Idempotent: an existing group is success, not an error."""
        try:
            self.command("XGROUP", "CREATE", key, group, start, "MKSTREAM")
            return True
        except RedisError as exc:
            if "BUSYGROUP" in str(exc):
                return False
            raise

    def xreadgroup(self, key: str, group: str, consumer: str, *, count: int = 1,
                   block_ms: int = 0, last: str = ">") -> list:
        args = ["XREADGROUP", "GROUP", group, consumer, "COUNT", count]
        if block_ms:
            args += ["BLOCK", block_ms]
        args += ["STREAMS", key, last]
        # Outlast the server-side block, or the client times out first and the
        # dropped socket loses the consumer's place in the group.
        budget = None if not block_ms else (block_ms / 1000.0) + self._timeout
        reply = self.command(*args, timeout=budget)
        return _entries(reply)

    def xack(self, key: str, group: str, entry_id: str) -> int:
        return int(self.command("XACK", key, group, entry_id))

    def xautoclaim(self, key: str, group: str, consumer: str, min_idle_ms: int,
                   *, start: str = "0-0", count: int = 8) -> list:
        """Reclaim entries whose owner stopped without acknowledging.

        This is the pending-work recovery path: a killed executor leaves its
        entries in the group's pending list, and the next executor claims them
        once they have been idle longer than the lease.
        """
        reply = self.command("XAUTOCLAIM", key, group, consumer, min_idle_ms,
                             start, "COUNT", count)
        if not isinstance(reply, list) or len(reply) < 2:
            return []
        return _pairs(reply[1])

    def xlen(self, key: str) -> int:
        return int(self.command("XLEN", key))

    def xrange(self, key: str, start: str = "-", end: str = "+",
               *, count: int | None = None) -> list:
        args = ["XRANGE", key, start, end]
        if count is not None:
            args += ["COUNT", count]
        return _pairs(self.command(*args))

    def set(self, key: str, value: str, *, nx: bool = False,
            ex: int | None = None) -> bool:
        args = ["SET", key, value]
        if ex is not None:
            args += ["EX", ex]
        if nx:
            args.append("NX")
        return self.command(*args) is not None

    def get(self, key: str) -> str | None:
        return _text_or_none(self.command("GET", key))

    def delete(self, *keys: str) -> int:
        return int(self.command("DEL", *keys))

    def expire(self, key: str, seconds: int) -> bool:
        return bool(self.command("EXPIRE", key, seconds))

    def eval(self, script: str, keys: list, args: list):
        """Run a Lua script server-side, which is how a multi-key operation
        becomes atomic.

        AF-005 needs three of these and cannot be correct without them: a
        lease may only be extended or released by its current owner, and the
        dispatch entry and its receipt must land together or not at all. Both
        are read-then-write races that `WATCH`/`MULTI` could also solve, but
        only by adding a retry loop and a second round trip for something Redis
        already executes atomically.

        `EVAL` is sent rather than `EVALSHA`: the scripts here are a few lines,
        run once per attempt, and skipping the script cache removes a NOSCRIPT
        fallback path that would otherwise need its own handling.
        """
        return self.command("EVAL", script, len(keys), *keys, *args)


def _text(value) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def _text_or_none(value) -> str | None:
    return None if value is None else _text(value)


def _fields(flat) -> dict:
    """Redis returns a field/value array; a stream entry is a mapping."""
    if not isinstance(flat, list):
        return {}
    pairs = zip(flat[::2], flat[1::2])
    return {_text(name): _text(value) for name, value in pairs}


def _pairs(entries) -> list:
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        if isinstance(entry, list) and len(entry) == 2 and entry[0] is not None:
            out.append((_text(entry[0]), _fields(entry[1])))
    return out


def _entries(reply) -> list:
    """Flatten XREADGROUP's stream/entries nesting into (id, fields) pairs."""
    if not isinstance(reply, list):
        return []
    out = []
    for stream in reply:
        if isinstance(stream, list) and len(stream) == 2:
            out.extend(_pairs(stream[1]))
    return out
