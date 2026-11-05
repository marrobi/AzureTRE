import React, { useCallback, useEffect, useState } from "react";
import {
  CommandBar,
  DetailsList,
  DetailsListLayoutMode,
  IColumn,
  ICommandBarItemProps,
  Link,
  SelectionMode,
  Shimmer,
  Stack,
  Text,
} from "@fluentui/react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ErrorBar } from "../components/ErrorBar";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, formatDuration } from "../format";
import { Run, TERMINAL_STATUSES } from "../types";

const POLL_MS = 15000;

export const RunsPage: React.FunctionComponent = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>();
  const [error, setError] = useState<string>();

  const load = useCallback(() => {
    api
      .get<Run[]>("/api/runs")
      .then((r) => {
        setRuns(r);
        setError(undefined);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const commands: ICommandBarItemProps[] = [
    { key: "start", text: "Start a run", iconProps: { iconName: "Play" }, onClick: () => { navigate("/pipelines"); } },
    { key: "refresh", text: "Refresh", iconProps: { iconName: "Refresh" }, onClick: load },
  ];

  const columns: IColumn[] = [
    { key: "status", name: "Status", minWidth: 150, maxWidth: 190, onRender: (r: Run) => <StatusBadge status={r.status} /> },
    {
      key: "run",
      name: "Run",
      minWidth: 180,
      isResizable: true,
      onRender: (r: Run) => (
        <Link
          href={`/runs/${r.id}`}
          onClick={(e) => {
            e.preventDefault();
            navigate(`/runs/${r.id}`);
          }}
        >
          {r.label || r.nextflow_run_name || r.id}
        </Link>
      ),
    },
    { key: "pipeline", name: "Pipeline", fieldName: "pipeline_name", minWidth: 140, isResizable: true },
    { key: "by", name: "Started by", fieldName: "created_by_name", minWidth: 120, isResizable: true },
    { key: "created", name: "Created", minWidth: 150, onRender: (r: Run) => formatDate(r.created_at) },
    {
      key: "duration",
      name: "Duration",
      minWidth: 80,
      onRender: (r: Run) =>
        formatDuration(r.started_at, TERMINAL_STATUSES.includes(r.status) ? r.finished_at : null),
    },
  ];

  return (
    <Stack tokens={{ childrenGap: 10 }}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <h1>Runs</h1>
        <CommandBar items={commands} />
      </Stack>
      <ErrorBar error={error} />
      {!runs && !error && <Shimmer />}
      {runs && runs.length === 0 && (
        <Text className="nf-muted">No runs yet. Choose a pipeline to start your first run.</Text>
      )}
      {runs && runs.length > 0 && (
        <DetailsList
          items={runs}
          columns={columns}
          selectionMode={SelectionMode.none}
          layoutMode={DetailsListLayoutMode.justified}
          getKey={(r: Run) => r.id}
          onItemInvoked={(r: Run) => navigate(`/runs/${r.id}`)}
        />
      )}
    </Stack>
  );
};
