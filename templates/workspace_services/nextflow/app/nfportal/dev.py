"""Simulated head runner for local development (NF_DEV_MODE=true). Not used in Azure."""

import json
import threading
import time
from datetime import datetime, timezone

from .batch import HeadStatus
from .store import RESULTS, RUNS, Store

STEP_SECONDS = 2.0


class SimulatedHeadRunner:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.tasks: dict[str, dict] = {}
        self.lock = threading.Lock()

    def submit(self, run_id: str, env: dict[str, str]) -> None:
        with self.lock:
            self.tasks[run_id] = {
                "state": "queued",
                "start": None,
                "end": None,
                "exit": None,
                "cancel": False,
                "log": [],
            }
        threading.Thread(target=self._simulate, args=(run_id,), daemon=True).start()

    def status(self, run_id: str) -> HeadStatus:
        task = self.tasks.get(run_id)
        if not task:
            return HeadStatus("unknown")
        return HeadStatus(task["state"], task["exit"], task["start"], task["end"])

    def cancel(self, run_id: str) -> None:
        if run_id in self.tasks:
            self.tasks[run_id]["cancel"] = True

    def read_log(self, run_id: str) -> str:
        return "\n".join(self.tasks.get(run_id, {}).get("log", []))

    def _event(self, run_id: str, event: str, **extra) -> None:
        payload = {
            "runName": "simulated_tre",
            "runId": run_id,
            "event": event,
            "utcTime": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        self.store.append_line(RUNS, f"{run_id}/events.jsonl", json.dumps(payload))

    def _log(self, run_id: str, line: str) -> None:
        self.tasks[run_id]["log"].append(f"{datetime.now():%H:%M:%S} {line}")

    def _simulate(self, run_id: str) -> None:
        task = self.tasks[run_id]
        time.sleep(STEP_SECONDS)
        task["state"], task["start"] = "running", datetime.now(timezone.utc)
        self._log(run_id, "N E X T F L O W  ~  version 26.10.5 (simulated)")
        self._event(run_id, "started", metadata={"workflow": {"start": task["start"].isoformat()}})
        params = json.loads(self.store.read_bytes(RUNS, f"{run_id}/params.json") or b"{}")
        samples = [f"sample_{i + 1}" for i in range(int(params.get("samples", 3)))]
        for n, sample in enumerate(samples):
            if task["cancel"]:
                break
            trace = {"task_id": n + 1, "process": "SIMULATE", "name": f"SIMULATE ({sample})"}
            self._event(run_id, "process_submitted", trace={**trace, "status": "SUBMITTED"})
            self._log(run_id, f"[{n + 1:02d}] Submitted process > SIMULATE ({sample})")
            time.sleep(STEP_SECONDS / 2)
            self._event(run_id, "process_started", trace={**trace, "status": "RUNNING"})
            time.sleep(STEP_SECONDS / 2)
            self._event(run_id, "process_completed", trace={**trace, "status": "COMPLETED"})
        if not task["cancel"]:
            trace = {"task_id": len(samples) + 1, "process": "SUMMARISE", "name": "SUMMARISE"}
            self._event(run_id, "process_submitted", trace={**trace, "status": "SUBMITTED"})
            time.sleep(STEP_SECONDS)
            self._event(run_id, "process_completed", trace={**trace, "status": "COMPLETED"})
            self._write_results(run_id, samples)
        self._event(run_id, "completed", metadata={"workflow": {"success": not task["cancel"]}})
        self._log(run_id, "Workflow completed" if not task["cancel"] else "Workflow aborted")
        task["state"], task["end"] = "completed", datetime.now(timezone.utc)
        task["exit"] = 143 if task["cancel"] else 0

    def _write_results(self, run_id: str, samples: list[str]) -> None:
        rows = "\n".join(f"{s},50,{i * 0.7:.3f},{-i:.3f},{i * 2:.3f},{i * 1.1:.3f}" for i, s in enumerate(samples))
        self.store.write_bytes(RESULTS, f"{run_id}/summary.csv", f"sample,steps,mean,min,max,final\n{rows}\n".encode())
        bars = "".join(
            f'<rect x="{40 + i * 60}" y="{200 - i * 30}" width="40" height="{i * 30 + 10}" fill="#0078d4"/>'
            for i, _ in enumerate(samples)
        )
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 220">{bars}</svg>'
        self.store.write_bytes(RESULTS, f"{run_id}/trajectories.svg", svg.encode())
        self.store.write_bytes(
            RESULTS,
            f"{run_id}/report.html",
            f"<h1>Simulated report</h1>{svg}<script>document.body.append('scripts run')</script>".encode(),
        )
        self.store.write_bytes(RESULTS, f"{run_id}/README.md", b"# Simulated run\n\n- Results are **simulated**.\n")
        self.store.write_bytes(
            RESULTS, f"{run_id}/_nextflow/nextflow.log", "\n".join(self.tasks[run_id]["log"]).encode()
        )
        self.store.write_bytes(RESULTS, f"{run_id}/_nextflow/exit_code", b"0\n")
