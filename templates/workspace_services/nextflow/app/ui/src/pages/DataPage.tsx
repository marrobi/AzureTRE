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
  SearchBox,
  Shimmer,
  Stack,
  Text,
  TextField,
} from "@fluentui/react";
import { api, fileUrl } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { FileList } from "../components/FileList";
import { FilePreview } from "../components/FilePreview";
import { formatSize } from "../format";
import { Me, StoredFile } from "../types";

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
    help: "One folder per pipeline. Upload main.nf and nextflow_schema.json into a folder, and subfolders such as templates/ by setting the folder path.",
  },
  {
    key: "results",
    title: "Results",
    writable: false,
    help: "Files published by runs. To take results out of the workspace, use an Airlock export request.",
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
  const [filter, setFilter] = useState("");
  const [folder, setFolder] = useState("");
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
    form.append("folder", folder);
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

  const shown = files?.filter((f) => f.name.toLowerCase().includes(filter.toLowerCase()));
  return (
    <Stack tokens={{ childrenGap: 12 }}>
      <MessageBar>{area.help}</MessageBar>
      {area.writable && (
        <Card>
          <Text variant="large">Upload</Text>
          <Stack horizontal wrap verticalAlign="end" tokens={{ childrenGap: 12 }}>
            <TextField
              label="Folder"
              placeholder={area.key === "pipelines" ? "my-pipeline" : "optional/folder"}
              value={folder}
              onChange={(_, v) => setFolder(v ?? "")}
              className="nf-folder"
            />
            <PrimaryButton
              text="Choose files"
              iconProps={{ iconName: "Upload" }}
              disabled={!!uploading || (area.key === "pipelines" && !folder.trim())}
              onClick={() => input.current?.click()}
            />
            <input ref={input} type="file" multiple hidden onChange={(e) => upload(e.target.files)} />
          </Stack>
          {area.key === "pipelines" && !folder.trim() && (
            <Text variant="small" className="nf-muted">
              Enter the pipeline folder name first.
            </Text>
          )}
          {uploading && <ProgressIndicator label={`Uploading ${uploading}`} />}
        </Card>
      )}
      {message && (
        <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setMessage(undefined)}>
          {message}
        </MessageBar>
      )}
      <ErrorBar error={error} onDismiss={() => setError(undefined)} />
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <SearchBox placeholder="Filter files" value={filter} onChange={(_, v) => setFilter(v ?? "")} className="nf-search" />
        <DefaultButton text="Refresh" iconProps={{ iconName: "Refresh" }} onClick={load} />
      </Stack>
      {!shown && !error && <Shimmer />}
      {shown && (
        <FileList
          files={shown}
          onSelect={setPreview}
          emptyMessage={filter ? "No files match the filter." : "No files yet."}
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
