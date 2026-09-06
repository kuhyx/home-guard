"""An in-memory fake conforming to crdt_sync's RemoteStore protocol, for tests."""

from __future__ import annotations

from crdt_sync import RemoteSyncError


class FakeRemoteStore:
    """Minimal in-memory stand-in; raises RemoteSyncError when told to fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self._files: dict[str, str] = {}
        self.fail = fail

    def list_directory(self, path: str) -> list[str]:
        if self.fail:
            msg = "fake outage"
            raise RemoteSyncError(msg)
        prefix = f"{path}/"
        return [k[len(prefix) :] for k in self._files if k.startswith(prefix)]

    def get_file_text(self, path: str) -> str | None:
        if self.fail:
            msg = "fake outage"
            raise RemoteSyncError(msg)
        return self._files.get(path)

    def put_file_text(self, path: str, text: str, *, message: str = "") -> None:
        if self.fail:
            msg = "fake outage"
            raise RemoteSyncError(msg)
        self._files[path] = text

    def delete_file(self, path: str, *, message: str = "") -> None:
        if self.fail:
            msg = "fake outage"
            raise RemoteSyncError(msg)
        self._files.pop(path, None)

    def can_access_remote(self) -> bool:
        return not self.fail

    def close(self) -> None:
        return None
