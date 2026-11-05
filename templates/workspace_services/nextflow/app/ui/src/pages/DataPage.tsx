import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  IconButton,
  MessageBar,
  MessageBarType,
  Panel,
  PanelType,
  Pivot,
  PivotItem,
  PrimaryButton,
  ProgressIndicator,
  Shimmer,
  Stack,
  Text,
  TextField,
} from "@fluentui/react";
import { api, fileUrl } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { FileBrowser } from "../components/FileBrowser";
import { FilePreview } from "../components/FilePreview";
import { formatShortDate, formatSize } from "../format";
import { Me, Run, StoredFile } from "../types";

const AREAS = [
  {
    key: "inputs",
    title: "Inputs",
    writable: true,
    help: "Files that pipelines can read. Data must already be inside the workspace, for example an approved Airlock import.",
  },
  {
    key: "pipelines",
    title: "Pipelines",
    writable: true,
    help: "One folder per pipeline. Create a folder, then upload main.nf and nextflow_schema.json into it. Use New folder for subfolders such as templates/.",
  },
  {
    key: "results",
    title: "Results",
    writable: false,
    help: "Files published by runs, in one folder per run. To take results out of the workspace, use an Airlock export request.",
  },
];

export const DataPage: React.FunctionComponent<{ me?: Me }> = ({ me }) => {
  const [area, setArea] = useState("inputs");
  return (
    <Stack tokens={{ childrenGap: 12 }}>
      <h1>Data</h1>
      <Pivot selectedKey={area} onLinkClick={(item) => item?.props.itemKey && setArea(item.props.itemKey)}>
        {AREAS.map((a) => (
          <PivotItem key={a.key} itemKey={a.key} headerText={a.title} />
        ))}
      </Pivot>
      <StorageArea key={area} area={AREAS.find((a) => a.key === area)!} maxUpload={me?.max_upload_bytes} />
    </Stack>
  );
};

const StorageArea: React.FunctionComponent<{ area: (typeof AREAS)[number]; maxUpload?: number }> = ({
  area,
  maxUpload,
}) => {
  const [files, setFiles] = useState<StoredFile[]>();
  const [runLabels, setRunLabels] = useState<Record<string, string>>({});
  const [path, setPath] = useState("");
  const [newFolder, setNewFolder] = useState<string>();
  const [preview, setPreview] = useState<StoredFile>();
  const [toDelete, setToDelete] = useState<StoredFile>();
  const [uploading, setUploading] = useState<string>();
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api
      .get<StoredFile[]>(`/api/storage/${area.key}`)
      .then(setFiles)
      .catch((e) => setError(e.message));
    if (area.key === "results") {
      api
        .get<Run[]>("/api/runs")
        .then((runs) =>
          setRunLabels(
            Object.fromEntries(
              runs.map((r) => [r.id, `${r.label || r.nextflow_run_name || r.id} · ${r.pipeline_name} · ${formatShortDate(r.created_at)}`]),
            ),
          ),
        )
        .catch(() => setRunLabels({}));
    }
  }, [area.key]);

  useEffect(load, [load]);

  const upload = async (list: FileList | null) => {
    if (!list?.length) return;
    const chosen = Array.from(list);
    const tooBig = chosen.find((f) => maxUpload && f.size > maxUpload);
    if (tooBig) {
      setError(`${tooBig.name} is larger than the ${formatSize(maxUpload)} upload limit.`);
      return;
    }
    const form = new FormData();
    chosen.forEach((f) => form.append("files", f));
    form.append("folder", path);
    setUploading(chosen.length === 1 ? chosen[0].name : `${chosen.length} files`);
    setError(undefined);
    try {
      const result = await api.upload<{ uploaded: string[] }>(`/api/storage/${area.key}`, form);
      setMessage(`Uploaded ${result.uploaded.join(", ")}`);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(undefined);
      if (input.current) input.current.value = "";
    }
  };

  const remove = async () => {
    const file = toDelete;
    setToDelete(undefined);
    if (!file) return;
    try {
      await api.delete(`/api/storage/${area.key}?name=${encodeURIComponent(file.name)}`);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const createFolder = () => {
    const name = (newFolder ?? "").trim().replace(/^\/+|\/+$/g, "");
    setNewFolder(undefined);
    // Blob storage has no empty folders: the folder exists once a file is uploaded into it.
    if (name && /^[A-Za-z0-9._ -]+(\/[A-Za-z0-9._ -]+)*$/.test(name)) setPath(`${path}${name}/`);
    else if (name) setError("Folder names can contain letters, numbers, spaces, dots, hyphens and underscores.");
  };

  const needsFolder = area.key === "pipelines" && !path;
  return (
    <Stack tokens={{ childrenGap: 12 }}>
      <MessageBar>{area.help}</MessageBar>
      {message && (
        <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setMessage(undefined)}>
          {message}
        </MessageBar>
      )}
      <ErrorBar error={error} onDismiss={() => setError(undefined)} />
      <Card>
        <Stack horizontal wrap verticalAlign="center" tokens={{ childrenGap: 8 }}>
          {area.writable && (
            <>
              <PrimaryButton
                text={path ? `Upload to ${path}` : "Upload"}
                iconProps={{ iconName: "Upload" }}
                disabled={!!uploading || needsFolder}
                onClick={() => input.current?.click()}
              />
              <DefaultButton text="New folder" iconProps={{ iconName: "FabricNewFolder" }} onClick={() => setNewFolder("")} />
              <input ref={input} type="file" multiple hidden onChange={(e) => upload(e.target.files)} />
            </>
          )}
          <DefaultButton text="Refresh" iconProps={{ iconName: "Refresh" }} onClick={load} />
          {needsFolder && (
            <Text variant="small" className="nf-muted">
              Open a pipeline folder, or create one, to upload its files.
            </Text>
          )}
        </Stack>
        {uploading && <ProgressIndicator label={`Uploading ${uploading}`} />}
        {!files && !error && <Shimmer />}
        {files && (
          <FileBrowser
            files={files}
            rootLabel={area.title}
            path={path}
            onPathChange={setPath}
            onSelect={setPreview}
            folderLabels={runLabels}
            emptyMessage={path ? "This folder is empty. Upload files to add them." : "No files yet."}
            renderActions={(f) => (
              <Stack horizontal>
                <IconButton iconProps={{ iconName: "View" }} title="Preview" ariaLabel="Preview" onClick={() => setPreview(f)} />
                <IconButton
                  iconProps={{ iconName: "Download" }}
                  title="Download"
                  ariaLabel="Download"
                  href={fileUrl(area.key, f.name, true)}
                />
                {area.writable && (
                  <IconButton iconProps={{ iconName: "Delete" }} title="Delete" ariaLabel="Delete" onClick={() => setToDelete(f)} />
                )}
              </Stack>
            )}
          />
        )}
      </Card>
      <Panel
        isOpen={!!preview}
        type={PanelType.large}
        onDismiss={() => setPreview(undefined)}
        headerText="Preview"
        closeButtonAriaLabel="Close"
      >
        {preview && <FilePreview container={area.key} name={preview.name} />}
      </Panel>
      <Dialog
        hidden={newFolder === undefined}
        onDismiss={() => setNewFolder(undefined)}
        dialogContentProps={{ type: DialogType.normal, title: "New folder", subText: `Create a folder in ${area.title}/${path}` }}
      >
        <TextField
          label="Folder name"
          value={newFolder ?? ""}
          onChange={(_, v) => setNewFolder(v ?? "")}
          onKeyDown={(e) => e.key === "Enter" && createFolder()}
          autoFocus
        />
        <DialogFooter>
          <PrimaryButton text="Create" onClick={createFolder} />
          <DefaultButton text="Cancel" onClick={() => setNewFolder(undefined)} />
        </DialogFooter>
      </Dialog>
      <Dialog
        hidden={!toDelete}
        onDismiss={() => setToDelete(undefined)}
        dialogContentProps={{ type: DialogType.normal, title: "Delete file?", subText: toDelete?.name }}
      >
        <DialogFooter>
          <PrimaryButton text="Delete" onClick={remove} />
          <DefaultButton text="Cancel" onClick={() => setToDelete(undefined)} />
        </DialogFooter>
      </Dialog>
    </Stack>
  );
};
