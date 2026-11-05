import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  MessageBar,
  MessageBarType,
  PrimaryButton,
  ProgressIndicator,
  Shimmer,
  Stack,
  Text,
} from "@fluentui/react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { PipelineSummary } from "../types";

export const PipelinesPage: React.FunctionComponent = () => {
  const navigate = useNavigate();
  const [pipelines, setPipelines] = useState<PipelineSummary[]>();
  const [error, setError] = useState<string>();
  const [importing, setImporting] = useState<string>();
  const [imported, setImported] = useState<string>();
  const [conflict, setConflict] = useState<File>();
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api
      .get<PipelineSummary[]>("/api/pipelines")
      .then(setPipelines)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const importZip = async (file: File, replace = false) => {
    setConflict(undefined);
    setError(undefined);
    setImported(undefined);
    setImporting(file.name);
    const form = new FormData();
    form.append("file", file);
    form.append("replace", String(replace));
    try {
      const result = await api.upload<{ name: string; files: string[] }>("/api/pipelines/import", form);
      setImported(`Imported ${result.name} (${result.files.length} files).`);
      load();
    } catch (e) {
      if ((e as ApiError).status === 409) setConflict(file);
      else setError((e as Error).message);
    } finally {
      setImporting(undefined);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <h1>Pipelines</h1>
        <PrimaryButton
          text="Import pipeline (.zip)"
          iconProps={{ iconName: "Upload" }}
          disabled={!!importing}
          onClick={() => input.current?.click()}
        />
        <input
          ref={input}
          type="file"
          accept=".zip,application/zip"
          hidden
          onChange={(e) => e.target.files?.[0] && importZip(e.target.files[0])}
        />
      </Stack>
      <MessageBar>
        To add a pipeline, import a zip of its folder, for example one approved through an Airlock import, or upload
        the folder to <b>Pipelines</b> on the Data page. The folder needs a{" "}
        <code>main.nf</code>, and a <code>nextflow_schema.json</code> to generate the launch form. Every process must
        set a <code>container</code>; the workspace can only pull Docker Hub images through the TRE Nexus proxy.
      </MessageBar>
      {importing && <ProgressIndicator label={`Importing ${importing}`} />}
      {imported && (
        <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setImported(undefined)}>
          {imported}
        </MessageBar>
      )}
      <ErrorBar error={error} onDismiss={() => setError(undefined)} />
      <Dialog
        hidden={!conflict}
        onDismiss={() => setConflict(undefined)}
        dialogContentProps={{
          type: DialogType.normal,
          title: "Replace pipeline?",
          subText: "A pipeline with this name already exists. Replace its files with the ones in the zip?",
        }}
      >
        <DialogFooter>
          <PrimaryButton text="Replace" onClick={() => conflict && importZip(conflict, true)} />
          <DefaultButton text="Cancel" onClick={() => setConflict(undefined)} />
        </DialogFooter>
      </Dialog>
      {!pipelines && !error && <Shimmer />}
      <Stack horizontal wrap tokens={{ childrenGap: 20 }}>
        {pipelines?.map((p) => (
          <Card key={p.id} className="nf-pipeline-card">
            <Text variant="xLarge">{p.name}</Text>
            <Text variant="small" className="nf-muted">
              {p.source === "builtin" ? "Built in" : `Workspace storage: pipelines/${p.id.split(":")[1]}`}
            </Text>
            <Text className="nf-grow">{p.description || "No description."}</Text>
            <Stack horizontal horizontalAlign="end">
              <PrimaryButton
                text="Launch"
                iconProps={{ iconName: "Play" }}
                onClick={() => navigate(`/pipelines/${encodeURIComponent(p.id)}/launch`)}
              />
            </Stack>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
};
