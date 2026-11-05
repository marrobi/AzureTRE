"""Runs the Nextflow head process for each run as an Azure Batch container task."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

HEAD_JOB_ID = "nfportal-head"
HEAD_COMMAND = "/opt/nfportal/head/run-head.sh"
LOG_TAIL_BYTES = 256 * 1024


@dataclass(frozen=True)
class HeadStatus:
    state: str  # queued | starting | running | completed | unknown
    exit_code: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    failure: str | None = None


class HeadRunner(Protocol):
    def submit(self, run_id: str, env: dict[str, str]) -> None: ...
    def status(self, run_id: str) -> HeadStatus: ...
    def cancel(self, run_id: str) -> None: ...
    def read_log(self, run_id: str) -> str: ...


def task_id(run_id: str) -> str:
    return f"run-{run_id}"


class AzureBatchHeadRunner:
    def __init__(self, endpoint: str, credential, pool_id: str, image: str) -> None:
        from azure.batch import BatchClient

        self.client = BatchClient(endpoint=endpoint, credential=credential)
        self.pool_id = pool_id
        self.image = image
        self._job_ready = False

    def _ensure_job(self) -> None:
        from azure.batch import models
        from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

        if self._job_ready:
            return
        try:
            self.client.get_job(HEAD_JOB_ID)
        except ResourceNotFoundError:
            try:
                self.client.create_job(
                    models.BatchJobCreateOptions(
                        id=HEAD_JOB_ID,
                        display_name="Nextflow portal head processes",
                        pool_info=models.BatchPoolInfo(pool_id=self.pool_id),
                    )
                )
            except ResourceExistsError:
                pass
        self._job_ready = True

    def submit(self, run_id: str, env: dict[str, str]) -> None:
        from azure.batch import models

        self._ensure_job()
        self.client.create_task(
            HEAD_JOB_ID,
            models.BatchTaskCreateOptions(
                id=task_id(run_id),
                display_name=f"Nextflow run {run_id}",
                command_line=HEAD_COMMAND,
                container_settings=models.BatchTaskContainerSettings(
                    image_name=self.image,
                    container_run_options="--rm",
                    working_directory=models.ContainerWorkingDirectory.TASK_WORKING_DIRECTORY,
                ),
                environment_settings=[models.EnvironmentSetting(name=k, value=v) for k, v in env.items()],
                constraints=models.BatchTaskConstraints(max_task_retry_count=0, max_wall_clock_time=timedelta(days=7)),
            ),
        )

    def status(self, run_id: str) -> HeadStatus:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            task = self.client.get_task(HEAD_JOB_ID, task_id(run_id))
        except ResourceNotFoundError:
            return HeadStatus(state="unknown")
        info = task.execution_info
        state = {"active": "queued", "preparing": "starting", "running": "running", "completed": "completed"}.get(
            str(task.state.value if hasattr(task.state, "value") else task.state), "unknown"
        )
        failure = None
        if info and info.failure_info:
            failure = info.failure_info.message or info.failure_info.code
        return HeadStatus(
            state=state,
            exit_code=info.exit_code if info else None,
            start_time=info.start_time if info else None,
            end_time=info.end_time if info else None,
            failure=failure,
        )

    def cancel(self, run_id: str) -> None:
        self.client.terminate_task(HEAD_JOB_ID, task_id(run_id))

    def read_log(self, run_id: str) -> str:
        from azure.core.exceptions import HttpResponseError

        try:
            props = self.client.get_task_file_properties(HEAD_JOB_ID, task_id(run_id), "stdout.txt")
            size = int(getattr(props, "content_length", 0) or 0)
            kwargs = {"ocp_range": f"bytes={size - LOG_TAIL_BYTES}-{size - 1}"} if size > LOG_TAIL_BYTES else {}
            data = b"".join(self.client.download_task_file(HEAD_JOB_ID, task_id(run_id), "stdout.txt", **kwargs))
        except HttpResponseError:
            return ""
        return data.decode("utf-8", "replace")
