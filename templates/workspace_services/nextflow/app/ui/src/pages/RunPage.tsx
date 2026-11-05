import React, { useCallback, useEffect, useState } from "react";
import {
  DefaultButton,
  DetailsList,
  DetailsListLayoutMode,
  Dialog,
  DialogFooter,
  DialogType,
  IColumn,
  MessageBar,
  MessageBarType,
  Pivot,
  PivotItem,
  PrimaryButton,
  ProgressIndicator,
  SelectionMode,
  Shimmer,
  Stack,
  Text,
} from "@fluentui/react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { FileList } from "../components/FileList";
import { FilePreview } from "../components/FilePreview";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, formatDuration } from "../format";
import { ProcessProgress, Run, StoredFile, TERMINAL_STATUSES } from "../types";

const POLL_MS = 5000;
const REPORTS = ["report.html", "timeline.html", "trace.txt", "dag.mmd", "nextflow.log", "params.json"];

export const RunPage: React.FunctionComponent = () => {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<Run>();
  const [error, setError] = useState<string>();
  const [confirmCancel, setConfirmCancel] = useState(false);
  const active = run ? !TERMINAL_STATUSES.includes(run.status) : true;

  const load = useCallback(() => {
    api
      .get<Run>(`/api/runs/${runId}`)
      .then((r) => {
        setRun(r);
        setError(undefined);
      })
      .catch((e) => setError(e.message));
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [active, load]);

  const cancel = async () => {
    setConfirmCancel(false);
    try {
      await api.post(`/api/runs/${runId}/cancel`);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!run) {
    return (
      <Stack tokens={{ childrenGap: 10 }}>
        <h1>Run {runId}</h1>
        <ErrorBar error={error} />
        {!error && <Shimmer />}
      </Stack>
    );
  }

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center" wrap>
        <Stack>
          <h1>{run.label || run.nextflow_run_name || `Run ${run.id}`}</h1>
          <Text className="nf-muted">
            {run.pipeline_name} · started by {run.created_by_name} · {formatDate(run.created_at)}
          </Text>
        </Stack>
        <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 16 }}>
          <StatusBadge status={run.status} />
          {active && !run.cancel_requested_by && (
            <DefaultButton text="Cancel run" iconProps={{ iconName: "Cancel" }} onClick={() => setConfirmCancel(true)} />
          )}
        </Stack>
      </Stack>
      <ErrorBar error={error} onDismiss={() => setError(undefined)} />
      {run.status === "failed" && run.error && (
        <MessageBar messageBarType={MessageBarType.error} isMultiline>
          {run.error}
        </MessageBar>
      )}
      {run.status === "queued" && (
        <MessageBar>
          Waiting for a Nextflow head node. The pool starts nodes on demand, which can take several minutes.
        </MessageBar>
      )}
      {active && run.cancel_requested_by && (
        <MessageBar messageBarType={MessageBarType.warning}>Cancel requested by {run.cancel_requested_by}.</MessageBar>
      )}
      <Pivot aria-label="Run details">
        <PivotItem headerText="Overview" itemIcon="Info">
          <Overview run={run} />
        </PivotItem>
        <PivotItem headerText="Results" itemIcon="FabricFolder">
          <Results run={run} active={active} />
        </PivotItem>
        <PivotItem headerText="Log" itemIcon="TextDocument">
          <Log run={run} active={active} />
        </PivotItem>
        <PivotItem headerText="Reports" itemIcon="ReportDocument">
          <Reports run={run} />
        </PivotItem>
      </Pivot>
      <Dialog
        hidden={!confirmCancel}
        onDismiss={() => setConfirmCancel(false)}
        dialogContentProps={{
          type: DialogType.normal,
          title: "Cancel this run?",
          subText: "Nextflow stops the run and its running tasks. Published results so far are kept.",
        }}
      >
        <DialogFooter>
          <PrimaryButton text="Cancel run" onClick={cancel} />
          <DefaultButton text="Keep running" onClick={() => setConfirmCancel(false)} />
        </DialogFooter>
      </Dialog>
    </Stack>
  );
};

const Overview: React.FunctionComponent<{ run: Run }> = ({ run }) => {
  const progress = run.progress ?? [];
  const params = Object.entries(run.params).map(([name, value]) => ({
    name,
    value: typeof value === "object" ? JSON.stringify(value) : String(value),
  }));
  const paramColumns: IColumn[] = [
    { key: "name", name: "Parameter", fieldName: "name", minWidth: 120, maxWidth: 220 },
    { key: "value", name: "Value", fieldName: "value", minWidth: 200, isMultiline: true },
  ];
  const ended = TERMINAL_STATUSES.includes(run.status);
  return (
    <Stack horizontal wrap tokens={{ childrenGap: 20 }} className="nf-tab">
      <Card className="nf-half">
        <Text variant="large">Progress</Text>
        {!progress.length && (
          <Text className="nf-muted">
            {ended ? "No task events were recorded." : "Tasks appear here once Nextflow submits them."}
          </Text>
        )}
        {progress.map((p) => (
          <ProcessBar key={p.name} p={p} />
        ))}
        <Stack tokens={{ childrenGap: 4 }} className="nf-facts">
          <Fact label="Run ID" value={run.id} />
          {run.nextflow_run_name && <Fact label="Nextflow run name" value={run.nextflow_run_name} />}
          <Fact label="Started" value={formatDate(run.started_at) || "Not yet"} />
          {run.finished_at && <Fact label="Finished" value={formatDate(run.finished_at)} />}
          <Fact label="Duration" value={formatDuration(run.started_at, ended ? run.finished_at : null)} />
          {run.exit_code !== null && <Fact label="Exit code" value={String(run.exit_code)} />}
        </Stack>
      </Card>
      <Card className="nf-half">
        <Text variant="large">Parameters</Text>
        <DetailsList
          items={params}
          columns={paramColumns}
          selectionMode={SelectionMode.none}
          layoutMode={DetailsListLayoutMode.justified}
          compact
        />
      </Card>
    </Stack>
  );
};

const ProcessBar: React.FunctionComponent<{ p: ProcessProgress }> = ({ p }) => {
  const done = p.succeeded + p.cached;
  const total = done + p.failed + p.running + p.submitted;
  const parts = [`${done} of ${total} done`];
  if (p.running) parts.push(`${p.running} running`);
  if (p.submitted) parts.push(`${p.submitted} waiting`);
  if (p.cached) parts.push(`${p.cached} cached`);
  if (p.failed) parts.push(`${p.failed} failed`);
  return (
    <ProgressIndicator
      label={p.name}
      description={parts.join(" · ")}
      percentComplete={total ? done / total : 0}
      className={p.failed ? "nf-progress-failed" : undefined}
    />
  );
};

const Fact: React.FunctionComponent<{ label: string; value: string }> = ({ label, value }) => (
  <Stack horizontal tokens={{ childrenGap: 8 }}>
    <Text className="nf-fact-label">{label}</Text>
    <Text>{value}</Text>
  </Stack>
);

const Results: React.FunctionComponent<{ run: Run; active: boolean }> = ({ run, active }) => {
  const prefix = `${run.id}/`;
  const [files, setFiles] = useState<StoredFile[]>();
  const [selected, setSelected] = useState<StoredFile>();
  const [error, setError] = useState<string>();

  const load = useCallback(() => {
    api
      .get<StoredFile[]>(`/api/storage/results?prefix=${encodeURIComponent(prefix)}`)
      .then((all) => setFiles(all.filter((f) => !f.name.startsWith(`${prefix}_nextflow/`))))
      .catch((e) => setError(e.message));
  }, [prefix]);

  useEffect(() => {
    load();
    if (!active) return;
    const timer = setInterval(load, POLL_MS * 3);
    return () => clearInterval(timer);
  }, [load, active]);

  useEffect(() => {
    if (!selected && files?.length) {
      setSelected(files.find((f) => f.kind === "html") ?? files.find((f) => f.kind !== "binary") ?? files[0]);
    }
  }, [files, selected]);

  return (
    <Stack horizontal wrap tokens={{ childrenGap: 20 }} className="nf-tab">
      <Card className="nf-file-pane">
        <Text variant="large">Published files</Text>
        <ErrorBar error={error} />
        {!files && !error && <Shimmer />}
        {files && (
          <FileList
            files={files}
            stripPrefix={prefix}
            selected={selected?.name}
            onSelect={setSelected}
            emptyMessage={active ? "Files appear here as the pipeline publishes them." : "This run published no files."}
          />
        )}
      </Card>
      {selected && (
        <Card className="nf-preview-pane">
          <FilePreview container="results" name={selected.name} label={selected.name.slice(prefix.length)} />
        </Card>
      )}
    </Stack>
  );
};

const Log: React.FunctionComponent<{ run: Run; active: boolean }> = ({ run, active }) => {
  const [log, setLog] = useState<string>();
  const [error, setError] = useState<string>();

  const load = useCallback(() => {
    api
      .get<string>(`/api/runs/${run.id}/log`)
      .then((text) => {
        setLog(text);
        setError(undefined);
      })
      .catch((e) => setError(e.message));
  }, [run.id]);

  useEffect(() => {
    load();
    if (!active) return;
    const timer = setInterval(load, POLL_MS * 2);
    return () => clearInterval(timer);
  }, [load, active]);

  return (
    <Stack tokens={{ childrenGap: 10 }} className="nf-tab">
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <Text className="nf-muted">
          {active ? "Nextflow console output from the head node. Refreshes automatically." : "Nextflow log for this run."}
        </Text>
        <DefaultButton text="Refresh" iconProps={{ iconName: "Refresh" }} onClick={load} />
      </Stack>
      <ErrorBar error={error} />
      {log === undefined && !error ? (
        <Shimmer />
      ) : (
        <pre className="nf-pre nf-log">{log || "No output yet."}</pre>
      )}
    </Stack>
  );
};

const Reports: React.FunctionComponent<{ run: Run }> = ({ run }) => {
  const prefix = `${run.id}/_nextflow/`;
  const [files, setFiles] = useState<StoredFile[]>();
  const [selected, setSelected] = useState<string>();

  useEffect(() => {
    api
      .get<StoredFile[]>(`/api/storage/results?prefix=${encodeURIComponent(prefix)}`)
      .then((all) => {
        const known = all.filter((f) => REPORTS.includes(f.name.slice(prefix.length)));
        setFiles(known);
        setSelected((s) => s ?? known.find((f) => f.name.endsWith("report.html"))?.name ?? known[0]?.name);
      })
      .catch(() => setFiles([]));
  }, [prefix, run.status]);

  if (!files) return <Shimmer />;
  if (!files.length) {
    return (
      <Text className="nf-muted nf-tab" block>
        Nextflow writes its execution report, timeline and trace when the run finishes.
      </Text>
    );
  }
  return (
    <Stack tokens={{ childrenGap: 12 }} className="nf-tab">
      <Stack horizontal wrap tokens={{ childrenGap: 8 }}>
        {files.map((f) => {
          const name = f.name.slice(prefix.length);
          return selected === f.name ? (
            <PrimaryButton key={f.name} text={name} />
          ) : (
            <DefaultButton key={f.name} text={name} onClick={() => setSelected(f.name)} />
          );
        })}
      </Stack>
      {selected && (
        <Card>
          <FilePreview container="results" name={selected} label={selected.slice(prefix.length)} />
        </Card>
      )}
    </Stack>
  );
};
