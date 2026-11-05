"""Pipeline catalogue and nf-core style parameter schemas."""

from __future__ import annotations

import json
import re
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from .store import INPUTS, PIPELINES, RESULTS, InvalidPath, Store, safe_blob_name

BUILTIN = "builtin"
STORAGE = "storage"
PATH_FORMATS = {"file-path", "directory-path", "path", "file-path-pattern"}
RESERVED_PARAMS = {"outdir"}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PATH_CONTAINERS = (INPUTS, RESULTS)
ZIP_MAX_FILES = 2000
ZIP_IGNORED = ("__MACOSX/", ".git/")
# A TRE overlay schema replaces the pipeline's own schema in the launch form, for example to hide
# options that need internet access. The pipeline still validates parameters against its own schema.
SCHEMA_FILES = ("tre_schema.json", "nextflow_schema.json")


@dataclass
class ParamField:
    name: str
    type: str
    title: str
    description: str = ""
    default: Any = None
    required: bool = False
    enum: list[Any] | None = None
    format: str | None = None
    group: str = "Parameters"
    hidden: bool = False
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None

    @property
    def is_path(self) -> bool:
        return self.format in PATH_FORMATS


@dataclass
class Pipeline:
    id: str
    name: str
    source: str
    description: str = ""
    readme: str = ""
    schema: dict | None = None
    fields: list[ParamField] = field(default_factory=list)


def schema_fields(schema: dict | None) -> list[ParamField]:
    """Flatten an nf-core nextflow_schema.json into form fields (draft-07 or 2020-12)."""
    if not schema:
        return []
    sections: list[tuple[str, dict]] = []
    defs = schema.get("$defs") or schema.get("definitions") or {}
    for key, section in defs.items():
        sections.append((section.get("title") or key, section))
    if schema.get("properties"):
        sections.append((schema.get("title") or "Parameters", schema))

    fields: list[ParamField] = []
    seen: set[str] = set()
    for group, section in sections:
        required = set(section.get("required") or [])
        for name, prop in (section.get("properties") or {}).items():
            if name in seen or name in RESERVED_PARAMS or not isinstance(prop, dict):
                continue
            seen.add(name)
            fields.append(
                ParamField(
                    name=name,
                    type=prop.get("type", "string") if isinstance(prop.get("type", "string"), str) else "string",
                    title=prop.get("title") or name,
                    description=prop.get("description") or prop.get("help_text") or "",
                    default=prop.get("default"),
                    required=name in required,
                    enum=prop.get("enum"),
                    format=prop.get("format"),
                    group=group,
                    hidden=bool(prop.get("hidden")),
                    pattern=prop.get("pattern"),
                    minimum=prop.get("minimum"),
                    maximum=prop.get("maximum"),
                )
            )
    return fields


def to_az_path(value: str, storage_container: str) -> str:
    """Convert an `inputs/...` or `results/...` selection to a Nextflow az:// path in this service's container."""
    value = value.strip()
    if value.startswith("az://"):
        value = value[len("az://") :]
        if value.startswith(f"{storage_container}/"):
            value = value[len(storage_container) + 1 :]
    container, _, rest = value.partition("/")
    if container not in PATH_CONTAINERS or not rest:
        raise InvalidPath("Choose a file or folder from the inputs or results storage.")
    return f"az://{storage_container}/{container}/{safe_blob_name(rest)}"


def coerce_params(
    fields: list[ParamField], raw: dict[str, Any], storage_container: str
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate form values against the schema fields. Returns (params, errors)."""
    params: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for f in fields:
        value = raw.get(f.name)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if f.required and f.default is None:
                errors[f.name] = "Required"
            continue
        try:
            if f.type == "boolean":
                value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
            elif f.type in ("integer", "number"):
                value = int(value) if f.type == "integer" else float(value)
                if f.minimum is not None and value < f.minimum:
                    raise ValueError(f"Must be at least {f.minimum:g}")
                if f.maximum is not None and value > f.maximum:
                    raise ValueError(f"Must be at most {f.maximum:g}")
            else:
                value = str(value)
                if f.is_path:
                    value = to_az_path(value, storage_container)
                    if f.pattern and not re.search(f.pattern, value):
                        raise ValueError("This file type isn't accepted here.")
                elif f.pattern and not re.fullmatch(f.pattern, value):
                    raise ValueError(f"Does not match pattern {f.pattern}")
            if f.enum and value not in f.enum:
                raise ValueError(f"Must be one of {', '.join(map(str, f.enum))}")
        except (TypeError, ValueError) as exc:
            errors[f.name] = str(exc) or "Invalid value"
            continue
        params[f.name] = value
    return params, errors


class PipelineCatalog:
    def __init__(self, store: Store, builtin_dir: Path) -> None:
        self.store = store
        self.builtin_dir = builtin_dir

    def list(self) -> list[Pipeline]:
        pipelines = [p for p in (self._builtin(d.name) for d in sorted(self.builtin_dir.glob("*"))) if p]
        names = sorted({i.name.split("/", 1)[0] for i in self.store.list(PIPELINES) if i.name.endswith("/main.nf")})
        pipelines += [p for p in (self._stored(n) for n in names) if p]
        return pipelines

    def get(self, pipeline_id: str) -> Pipeline | None:
        source, _, name = pipeline_id.partition(":")
        if not NAME_PATTERN.match(name):
            return None
        if source == BUILTIN:
            return self._builtin(name)
        if source == STORAGE:
            return self._stored(name)
        return None

    def _builtin(self, name: str) -> Pipeline | None:
        if not NAME_PATTERN.match(name):
            return None
        base = self.builtin_dir / name
        if not (base / "main.nf").is_file():
            return None
        schema_file = next((base / f for f in SCHEMA_FILES if (base / f).is_file()), None)
        schema = _load_json(schema_file.read_bytes() if schema_file else None)
        readme = (base / "README.md").read_text() if (base / "README.md").is_file() else ""
        return _pipeline(f"{BUILTIN}:{name}", name, BUILTIN, schema, readme)

    def _stored(self, name: str) -> Pipeline | None:
        if not NAME_PATTERN.match(name) or self.store.size(PIPELINES, f"{name}/main.nf") is None:
            return None
        schema = next(
            (s for s in (_load_json(self.store.read_bytes(PIPELINES, f"{name}/{f}")) for f in SCHEMA_FILES) if s), None
        )
        readme = (self.store.read_bytes(PIPELINES, f"{name}/README.md") or b"").decode("utf-8", "replace")
        return _pipeline(f"{STORAGE}:{name}", name, STORAGE, schema, readme)


def _load_json(data: bytes | None) -> dict | None:
    if not data:
        return None
    try:
        value = json.loads(data)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _pipeline(pid: str, name: str, source: str, schema: dict | None, readme: str) -> Pipeline:
    title = (schema or {}).get("title") or name
    description = (schema or {}).get("description") or ""
    return Pipeline(
        id=pid,
        name=title,
        source=source,
        description=description,
        readme=readme,
        schema=schema,
        fields=schema_fields(schema),
    )


class PipelineImportError(ValueError):
    pass


def import_pipeline_zip(
    store: Store, archive: BinaryIO, name: str, max_bytes: int, replace: bool = False
) -> tuple[str, list[str]]:
    """Extract a pipeline zip, such as an approved Airlock import, into pipelines/<name>/.

    If every file is inside one top-level folder, that folder is removed and gives the default name.
    Returns the pipeline name and the files written.
    """
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as exc:
        raise PipelineImportError("The file isn't a valid zip archive.") from exc
    with zf:
        members = [
            m
            for m in zf.infolist()
            if not m.is_dir() and not any(m.filename.startswith(p) or f"/{p}" in m.filename for p in ZIP_IGNORED)
        ]
        if not members or len(members) > ZIP_MAX_FILES:
            raise PipelineImportError(f"The zip must contain between 1 and {ZIP_MAX_FILES} files.")
        if sum(m.file_size for m in members) > max_bytes:
            raise PipelineImportError("The extracted pipeline is larger than the upload limit.")
        paths = []
        for m in members:
            if stat.S_ISLNK(m.external_attr >> 16):
                raise PipelineImportError(f"Symbolic links aren't allowed: {m.filename}")
            try:
                paths.append(safe_blob_name(m.filename))
            except InvalidPath as exc:
                raise PipelineImportError(f"Unsafe path in zip: {m.filename}") from exc
        tops = {p.split("/", 1)[0] for p in paths}
        strip = len(tops) == 1 and all("/" in p for p in paths)
        if strip:
            paths = [p.split("/", 1)[1] for p in paths]
        name = name.strip() or (tops.pop() if strip else "")
        if not NAME_PATTERN.match(name):
            raise PipelineImportError("Give the pipeline a name of letters, numbers, dots, dashes or underscores.")
        if "main.nf" not in paths:
            raise PipelineImportError("The zip needs a main.nf at its top level, or in a single top-level folder.")
        existing = [i.name for i in store.list(PIPELINES, f"{name}/")]
        if existing and not replace:
            raise PipelineImportError(f"A pipeline named {name} already exists.")
        for old in existing:
            store.delete(PIPELINES, old)
        written = []
        for m, path in zip(members, paths, strict=True):
            with zf.open(m) as src:
                store.write_stream(PIPELINES, f"{name}/{path}", src)
            written.append(path)
    return name, written
