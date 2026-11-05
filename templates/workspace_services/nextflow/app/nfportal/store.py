"""Blob storage access for pipelines, inputs, run state and results.

AzureBlobStore uses the portal's managed identity. LocalStore keeps the same
layout on disk for development and tests.
"""

from __future__ import annotations

import mimetypes
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

PIPELINES = "pipelines"
INPUTS = "inputs"
WORK = "work"
RESULTS = "results"
RUNS = "runs"
CONTAINERS = (PIPELINES, INPUTS, WORK, RESULTS, RUNS)
BROWSABLE = (INPUTS, RESULTS, PIPELINES)


@dataclass(frozen=True)
class BlobItem:
    name: str
    size: int
    last_modified: datetime | None


class InvalidPath(ValueError):
    pass


def safe_blob_name(name: str) -> str:
    """Normalise a user-supplied blob path and reject traversal or empty segments."""
    parts = PurePosixPath(name.replace("\\", "/").strip("/")).parts
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise InvalidPath(f"Invalid path: {name!r}")
    return "/".join(parts)


def content_type_for(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


class Store(Protocol):
    def read_bytes(self, container: str, name: str) -> bytes | None: ...
    def read_head(self, container: str, name: str, limit: int) -> bytes | None: ...
    def write_bytes(self, container: str, name: str, data: bytes) -> None: ...
    def write_stream(self, container: str, name: str, stream: BinaryIO) -> None: ...
    def append_line(self, container: str, name: str, line: str) -> None: ...
    def list(self, container: str, prefix: str = "") -> list[BlobItem]: ...
    def iter_bytes(self, container: str, name: str) -> Iterator[bytes]: ...
    def size(self, container: str, name: str) -> int | None: ...
    def delete(self, container: str, name: str) -> None: ...


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        for container in CONTAINERS:
            (root / container).mkdir(parents=True, exist_ok=True)

    def _path(self, container: str, name: str) -> Path:
        if container not in CONTAINERS:
            raise InvalidPath(f"Unknown container: {container}")
        return self.root / container / safe_blob_name(name)

    def read_bytes(self, container: str, name: str) -> bytes | None:
        path = self._path(container, name)
        return path.read_bytes() if path.is_file() else None

    def read_head(self, container: str, name: str, limit: int) -> bytes | None:
        path = self._path(container, name)
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            return handle.read(limit)

    def write_bytes(self, container: str, name: str, data: bytes) -> None:
        path = self._path(container, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write_stream(self, container: str, name: str, stream: BinaryIO) -> None:
        path = self._path(container, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            shutil.copyfileobj(stream, handle)

    def append_line(self, container: str, name: str, line: str) -> None:
        path = self._path(container, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip("\n") + "\n")

    def list(self, container: str, prefix: str = "") -> list[BlobItem]:
        base = self.root / container
        items = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.relative_to(base).as_posix()
            if name.startswith(prefix):
                stat = path.stat()
                items.append(BlobItem(name, stat.st_size, datetime.fromtimestamp(stat.st_mtime, timezone.utc)))
        return sorted(items, key=lambda i: i.name)

    def iter_bytes(self, container: str, name: str) -> Iterator[bytes]:
        with self._path(container, name).open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                yield chunk

    def size(self, container: str, name: str) -> int | None:
        path = self._path(container, name)
        return path.stat().st_size if path.is_file() else None

    def delete(self, container: str, name: str) -> None:
        path = self._path(container, name)
        if path.is_file():
            os.remove(path)


class AzureBlobStore:
    def __init__(self, account_url: str, credential) -> None:
        from azure.storage.blob import BlobServiceClient

        self.client = BlobServiceClient(account_url=account_url, credential=credential)

    def _blob(self, container: str, name: str):
        if container not in CONTAINERS:
            raise InvalidPath(f"Unknown container: {container}")
        return self.client.get_blob_client(container, safe_blob_name(name))

    def read_bytes(self, container: str, name: str) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._blob(container, name).download_blob().readall()
        except ResourceNotFoundError:
            return None

    def read_head(self, container: str, name: str, limit: int) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._blob(container, name).download_blob(offset=0, length=limit).readall()
        except ResourceNotFoundError:
            return None

    def write_bytes(self, container: str, name: str, data: bytes) -> None:
        from azure.storage.blob import ContentSettings

        self._blob(container, name).upload_blob(
            data, overwrite=True, content_settings=ContentSettings(content_type=content_type_for(name))
        )

    def write_stream(self, container: str, name: str, stream: BinaryIO) -> None:
        from azure.storage.blob import ContentSettings

        self._blob(container, name).upload_blob(
            stream,
            overwrite=True,
            max_concurrency=4,
            content_settings=ContentSettings(content_type=content_type_for(name)),
        )

    def append_line(self, container: str, name: str, line: str) -> None:
        from azure.core.exceptions import ResourceExistsError

        blob = self._blob(container, name)
        try:
            blob.create_append_blob(if_none_match="*")
        except ResourceExistsError:
            pass
        blob.append_block((line.rstrip("\n") + "\n").encode("utf-8"))

    def list(self, container: str, prefix: str = "") -> list[BlobItem]:
        if container not in CONTAINERS:
            raise InvalidPath(f"Unknown container: {container}")
        blobs = self.client.get_container_client(container).list_blobs(name_starts_with=prefix or None)
        return [BlobItem(b.name, b.size, b.last_modified) for b in blobs]

    def iter_bytes(self, container: str, name: str) -> Iterator[bytes]:
        yield from self._blob(container, name).download_blob().chunks()

    def size(self, container: str, name: str) -> int | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._blob(container, name).get_blob_properties().size
        except ResourceNotFoundError:
            return None

    def delete(self, container: str, name: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self._blob(container, name).delete_blob()
        except ResourceNotFoundError:
            pass
