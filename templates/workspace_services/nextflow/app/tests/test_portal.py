import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from nfportal.auth import User, safe_next, user_from_claims
from nfportal.batch import HeadStatus
from nfportal.config import load_settings
from nfportal.main import Services, create_app
from nfportal.pipelines import PipelineCatalog, coerce_params, schema_fields
from nfportal.runs import RunService
from nfportal.store import RESULTS, RUNS, WORK, LocalStore

ROLES = ("WorkspaceOwner", "WorkspaceResearcher")


def make_user(roles, oid="oid-1"):
    return User(id=oid, name="Ada", roles=tuple(roles))


class FakeAuth:
    def __init__(self, claims):
        self.claims = claims

    def start(self, redirect_uri):
        return "https://login.example/authorize", {"state": "s", "redirect_uri": redirect_uri}

    def finish(self, flow, query):
        if query.get("state") != flow["state"]:
            raise ValueError("state mismatch")
        return self.claims


class FakeRunner:
    def __init__(self):
        self.state = HeadStatus("queued")
        self.submitted, self.cancelled = [], []

    def submit(self, run_id, env):
        self.submitted.append((run_id, env))

    def status(self, run_id):
        return self.state

    def cancel(self, run_id):
        self.cancelled.append(run_id)

    def read_log(self, run_id):
        return "log"


@pytest.fixture
def services(tmp_path):
    settings = replace(
        load_settings(),
        dev_mode=False,
        storage_account="stnf",
        head_identity_client_id="cid",
        batch_endpoint="https://ba.region.batch.azure.com",
        data_dir=tmp_path,
        session_secret="x" * 32,
        public_url="https://nf.example",
    )
    store = LocalStore(tmp_path)
    runner = FakeRunner()
    svc = Services(
        settings, store, RunService(settings, store, runner), PipelineCatalog(store, settings.builtin_pipelines_dir)
    )
    svc.runner = runner
    return svc


def client(services, roles=ROLES):
    """Signs in through /auth/login and /auth/callback with a fake identity provider."""
    services.auth = FakeAuth({"oid": "oid-1", "name": "Ada", "roles": list(roles or [])})
    c = TestClient(create_app(services.settings, services), base_url="https://nf.example", follow_redirects=False)
    if roles is not None:
        login = c.get("/auth/login?next=/runs/abc")
        assert login.headers["location"] == "https://login.example/authorize"
        c.callback = c.get("/auth/callback?state=s&code=c")
    return c


def test_claims_require_workspace_role():
    assert user_from_claims({"oid": "a", "roles": ["WorkspaceResearcher"]}, ROLES).id == "a"
    assert user_from_claims({"oid": "a", "roles": ["Other"]}, ROLES) is None
    assert user_from_claims({"roles": ["WorkspaceOwner"]}, ROLES) is None


def test_sign_in_flow_and_rejections(services):
    anonymous = client(services, roles=None)
    assert anonymous.get("/api/runs").status_code == 401
    assert anonymous.get("/runs").headers["location"] == "/auth/login?next=/runs"
    assert anonymous.get("/healthz").status_code == 200
    assert anonymous.get("/auth/callback?state=s&code=c").headers["location"] == "/auth/login"

    no_role = client(services, roles=["Other"])
    assert no_role.callback.status_code == 403
    assert no_role.get("/api/runs").status_code == 401

    member = client(services)
    assert member.callback.headers["location"] == "/runs/abc"
    assert member.get("/api/runs").status_code == 200
    assert member.get("/auth/logout").status_code == 200
    assert member.get("/api/runs").status_code == 401


def test_safe_next_blocks_open_redirects():
    assert safe_next("/runs/1?x=2") == "/runs/1?x=2"
    for bad in ("https://evil.example", "//evil.example", "/\\evil.example", "runs", None):
        assert safe_next(bad) == "/"


def test_schema_fields_flatten_nf_core_defs_and_skip_outdir():
    schema = {
        "$defs": {
            "in": {
                "title": "Input",
                "required": ["input"],
                "properties": {"input": {"type": "string", "format": "file-path"}, "outdir": {"type": "string"}},
            }
        },
        "properties": {"n": {"type": "integer", "minimum": 1}},
    }
    fields = schema_fields(schema)
    assert [(f.name, f.group, f.required, f.is_path) for f in fields] == [
        ("input", "Input", True, True),
        ("n", "Parameters", False, False),
    ]


def test_coerce_params_validates_paths_and_ranges():
    fields = schema_fields(
        {
            "properties": {
                "input": {"type": "string", "format": "file-path"},
                "reads": {"type": "string", "format": "file-path", "pattern": "^\\S+\\.f(ast)?q(\\.gz)?$"},
                "n": {"type": "integer", "minimum": 2, "maximum": 5},
                "title": {"type": "string", "pattern": "^[a-z]+$"},
            }
        }
    )
    params, errors = coerce_params(fields, {"input": "inputs/a/b.txt", "n": "3", "title": "ok"}, "nextflow-ab12")
    assert params == {"input": "az://nextflow-ab12/inputs/a/b.txt", "n": 3, "title": "ok"} and not errors
    params, _ = coerce_params(fields, {"input": "az://nextflow-ab12/results/r1/x.csv"}, "nextflow-ab12")
    assert params["input"] == "az://nextflow-ab12/results/r1/x.csv"
    params, errors = coerce_params(fields, {"reads": "inputs/s/S1_R1.fastq.gz"}, "nextflow-ab12")
    assert params["reads"] == "az://nextflow-ab12/inputs/s/S1_R1.fastq.gz" and not errors
    _, errors = coerce_params(fields, {"reads": "results/r1/S1.bam"}, "nextflow-ab12")
    assert set(errors) == {"reads"}
    _, errors = coerce_params(fields, {"input": "runs/x/run.json", "n": 9, "title": "Bad!"}, "nextflow-ab12")
    assert set(errors) == {"input", "n", "title"}
    _, errors = coerce_params(fields, {"input": "inputs/../runs/x"}, "nextflow-ab12")
    assert "input" in errors


def test_run_lifecycle_and_progress(services):
    pipeline = services.catalog.get("builtin:tre-demo")
    run = services.runs.create(make_user(["WorkspaceResearcher"]), pipeline, {"samples": 2}, "label")
    assert run.params["outdir"] == f"az://nextflow/results/{run.id}"
    config = services.store.read_bytes(RUNS, f"{run.id}/nextflow.config").decode()
    assert "allowPoolCreation = false" in config and "clientId = 'cid'" in config
    assert "AZCOPY_JOB_PLAN_LOCATION = '$PWD/.azcopy'" in config
    assert f"workDir = 'az://nextflow/work/{run.id}'" in config
    assert services.runner.submitted[0][1]["NF_PIPELINE"] == "builtin:tre-demo"

    for event, status in (("process_submitted", "SUBMITTED"), ("process_completed", "COMPLETED")):
        services.store.append_line(
            RUNS,
            f"{run.id}/events.jsonl",
            json.dumps(
                {
                    "event": event,
                    "runName": "happy_turing",
                    "trace": {"task_id": 1, "process": "SIMULATE", "status": status},
                }
            ),
        )
    services.store.append_line(RUNS, f"{run.id}/events.jsonl", json.dumps({"event": "started"}))
    services.runner.state = HeadStatus("running")
    assert services.runs.refresh(run).status == "running"
    assert services.runs.progress(run.id)[0].succeeded == 1

    services.runner.state = HeadStatus("completed", exit_code=1, end_time=datetime.now(timezone.utc))
    run = services.runs.refresh(services.runs.get(run.id))
    assert (run.status, run.exit_code, run.nextflow_run_name) == ("failed", 1, "happy_turing")


def test_only_starter_or_owner_can_cancel(services):
    pipeline = services.catalog.get("builtin:tre-demo")
    starter = make_user(["WorkspaceResearcher"], "a")
    other = make_user(["WorkspaceResearcher"], "b")
    owner = make_user(["WorkspaceOwner"], "c")
    run = services.runs.create(starter, pipeline, {}, "")
    with pytest.raises(PermissionError):
        services.runs.cancel(run, other)
    services.runs.cancel(run, owner)
    assert services.runner.cancelled == [run.id]


def test_files_are_sandboxed_and_paths_restricted(services):
    services.store.write_bytes(RESULTS, "abc/report.html", b"<script>alert(1)</script>")
    services.store.write_bytes(RUNS, "abc/run.json", b"{}")
    services.store.write_bytes(RESULTS, "abc/.azure_blob_dir", b"")
    c = client(services)
    assert [f["name"] for f in c.get("/api/storage/results").json()] == ["abc/report.html"]
    response = c.get("/files/results/abc/report.html")
    assert response.status_code == 200
    assert response.headers["content-security-policy"].startswith("sandbox allow-scripts")
    assert c.get("/files/runs/abc/run.json").status_code == 404
    assert c.get("/files/results/abc/..%2F..%2Fruns/abc/run.json").status_code in (400, 404)


def test_mutations_require_csrf_header(services):
    c = client(services)
    assert c.post("/api/runs", json={"pipeline_id": "builtin:tre-demo"}).status_code == 403
    response = c.post(
        "/api/runs",
        json={"pipeline_id": "builtin:tre-demo", "params": {"steps": 1}},
        headers={"X-Requested-With": "nfportal"},
    )
    assert response.status_code == 422 and "steps" in response.json()["errors"]
    assert (
        c.post(
            "/api/storage/results", files={"files": ("a.txt", b"x")}, headers={"X-Requested-With": "nfportal"}
        ).status_code
        == 403
    )


def test_msal_client_starts_pkce_code_flow():
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit

    from nfportal.auth import MsalAuthClient

    tenant = "https://login.microsoftonline.com/tenant-id"
    metadata = {
        "authorization_endpoint": f"{tenant}/oauth2/v2.0/authorize",
        "token_endpoint": f"{tenant}/oauth2/v2.0/token",
        "issuer": f"{tenant}/v2.0",
    }

    class Http:
        def get(self, url, **kwargs):
            return SimpleNamespace(status_code=200, text=json.dumps(metadata), headers={})

        def post(self, url, **kwargs):
            raise AssertionError("no token request expected")

    client = MsalAuthClient("client-id", "secret", tenant, http_client=Http())
    auth_uri, flow = client.start("https://nf.example/auth/callback")
    query = parse_qs(urlsplit(auth_uri).query)
    assert query["redirect_uri"] == ["https://nf.example/auth/callback"]
    assert query["code_challenge_method"] == ["S256"] and "nonce" in query and flow["state"] == query["state"][0]


def test_tre_schema_overlay_replaces_pipeline_schema(tmp_path):
    pipeline = tmp_path / "builtin" / "upstream"
    pipeline.mkdir(parents=True)
    (pipeline / "main.nf").write_text("workflow {}")
    (pipeline / "nextflow_schema.json").write_text(json.dumps({"properties": {"pgs_id": {"type": "string"}}}))
    (pipeline / "tre_schema.json").write_text(json.dumps({"properties": {"scorefile": {"type": "string"}}}))
    catalog = PipelineCatalog(LocalStore(tmp_path / "store"), tmp_path / "builtin")
    assert [f.name for f in catalog.get("builtin:upstream").fields] == ["scorefile"]


def test_head_gets_tre_registry(services):
    services.runs.settings = replace(services.settings, runtime_image="acr.example.io/microsoft/azuretre/nf:1")
    run = services.runs.create(make_user(["WorkspaceOwner"]), services.catalog.get("builtin:tre-demo"), {}, "")
    env = dict(services.runner.submitted[-1][1])
    assert run.id == env["NF_RUN_ID"] and env["NF_CONTAINER_REGISTRY"] == "acr.example.io"


def test_expire_work_deletes_old_files_of_finished_runs_only(services, tmp_path):
    import os
    import time

    pipeline = services.catalog.get("builtin:tre-demo")
    done = services.runs.create(make_user(["WorkspaceOwner"]), pipeline, {}, "")
    active = services.runs.create(make_user(["WorkspaceOwner"]), pipeline, {}, "")
    services.runner.state = HeadStatus("completed", exit_code=0, end_time=datetime.now(timezone.utc))
    services.runs.refresh(services.runs.get(done.id))
    old = time.time() - 30 * 86400
    for run_id in (done.id, active.id):
        services.store.write_bytes(WORK, f"{run_id}/ab/task/.command.out", b"x")
        os.utime(tmp_path / WORK / run_id / "ab/task/.command.out", (old, old))
    services.store.write_bytes(WORK, f"{done.id}/cd/new/.command.out", b"x")
    assert services.runs.expire_work() == 1
    remaining = [i.name for i in services.store.list(WORK)]
    assert f"{done.id}/ab/task/.command.out" not in remaining
    assert f"{done.id}/cd/new/.command.out" in remaining and f"{active.id}/ab/task/.command.out" in remaining
