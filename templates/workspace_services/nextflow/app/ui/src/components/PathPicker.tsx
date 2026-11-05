import React, { useEffect, useMemo, useState } from "react";
import {
  DefaultButton,
  IconButton,
  Panel,
  PanelType,
  Pivot,
  PivotItem,
  PrimaryButton,
  Shimmer,
  Stack,
  Text,
  TextField,
  Toggle,
} from "@fluentui/react";
import { api } from "../api";
import { formatShortDate } from "../format";
import { ParamField, Run, StoredFile } from "../types";
import { ErrorBar } from "./ErrorBar";
import { FileBrowser } from "./FileBrowser";

const AREAS = [
  { key: "inputs", title: "Inputs" },
  { key: "results", title: "Results" },
];

/** Builds a file filter from the parameter's JSON schema pattern, if it's a valid JavaScript regex. */
function patternFilter(field: ParamField): ((name: string) => boolean) | undefined {
  if (!field.pattern) return undefined;
  try {
    const re = new RegExp(field.pattern);
    return (name) => re.test(name.split("/").pop() ?? name) || re.test(name);
  } catch {
    return undefined;
  }
}

export interface PathPickerProps {
  field: ParamField;
  value?: string;
  errorMessage?: string;
  runLabels: Record<string, string>;
  onChange: (value: string | undefined) => void;
}

export const PathPicker: React.FunctionComponent<PathPickerProps> = ({ field, value, errorMessage, runLabels, onChange }) => {
  const [open, setOpen] = useState(false);
  const isFolder = field.format === "directory-path";
  const [area, from] = value?.split("/", 2) ?? [];
  const runLabel = area === "results" && from ? runLabels[from] : undefined;

  return (
    <Stack>
      <Stack horizontal verticalAlign="end" tokens={{ childrenGap: 8 }}>
        <Stack.Item grow>
          <TextField
            label={field.title}
            required={field.required}
            invalid={!!errorMessage}
            placeholder={isFolder ? "No folder selected" : "No file selected"}
            value={value ?? ""}
            onChange={(_, v) => onChange(v || undefined)}
          />
        </Stack.Item>
        <Stack.Item>
          <Stack horizontal tokens={{ childrenGap: 4 }}>
            <DefaultButton text="Browse" iconProps={{ iconName: isFolder ? "FabricFolder" : "OpenFile" }} onClick={() => setOpen(true)} />
            {value && <IconButton iconProps={{ iconName: "Cancel" }} title="Clear" ariaLabel={`Clear ${field.title}`} onClick={() => onChange(undefined)} />}
          </Stack>
        </Stack.Item>
      </Stack>
      {errorMessage && <Text className="nf-error">{errorMessage}</Text>}
      {runLabel && <Text variant="small" className="nf-muted">From run {runLabel}</Text>}
      {field.description && <Text variant="small" className="nf-muted">{field.description}</Text>}
      {open && (
        <PathPanel
          field={field}
          value={value}
          runLabels={runLabels}
          onDismiss={() => setOpen(false)}
          onChoose={(v) => {
            onChange(v);
            setOpen(false);
          }}
        />
      )}
    </Stack>
  );
};

const PathPanel: React.FunctionComponent<{
  field: ParamField;
  value?: string;
  runLabels: Record<string, string>;
  onDismiss: () => void;
  onChoose: (value: string) => void;
}> = ({ field, value, runLabels, onDismiss, onChoose }) => {
  const isFolder = field.format === "directory-path";
  const [initialArea, ...rest] = (value ?? "").split("/");
  const startArea = AREAS.some((a) => a.key === initialArea) ? initialArea : "inputs";
  const [area, setArea] = useState(startArea);
  const [path, setPath] = useState(startArea === initialArea && rest.length > 1 ? `${rest.slice(0, -1).join("/")}/` : "");
  const [files, setFiles] = useState<StoredFile[]>();
  const [error, setError] = useState<string>();
  const matches = useMemo(() => patternFilter(field), [field]);
  const [showAll, setShowAll] = useState(!matches);

  useEffect(() => {
    setFiles(undefined);
    setError(undefined);
    api
      .get<StoredFile[]>(`/api/storage/${area}`)
      .then(setFiles)
      .catch((e) => setError(e.message));
  }, [area]);

  const shown = useMemo(() => {
    const all = (files ?? []).filter((f) => !(area === "results" && f.name.split("/")[1] === "_nextflow"));
    return showAll || !matches ? all : all.filter((f) => matches(f.name));
  }, [files, area, showAll, matches]);

  const changeArea = (key: string) => {
    setArea(key);
    setPath("");
  };

  return (
    <Panel
      isOpen
      type={PanelType.medium}
      headerText={isFolder ? `Choose a folder: ${field.title}` : `Choose a file: ${field.title}`}
      onDismiss={onDismiss}
      closeButtonAriaLabel="Close"
      isFooterAtBottom
      onRenderFooterContent={() => (
        <Stack horizontal tokens={{ childrenGap: 8 }}>
          {isFolder && (
            <PrimaryButton text="Use this folder" disabled={!path} onClick={() => onChoose(`${area}/${path.replace(/\/$/, "")}`)} />
          )}
          <DefaultButton text="Cancel" onClick={onDismiss} />
        </Stack>
      )}
    >
      <Stack tokens={{ childrenGap: 8 }}>
        <Pivot selectedKey={area} onLinkClick={(item) => item?.props.itemKey && changeArea(item.props.itemKey)}>
          {AREAS.map((a) => (
            <PivotItem key={a.key} itemKey={a.key} headerText={a.title} />
          ))}
        </Pivot>
        {matches && (
          <Toggle inlineLabel label="Show all files, not only those this parameter accepts" checked={showAll} onChange={(_, c) => setShowAll(!!c)} />
        )}
        <ErrorBar error={error} />
        {!files && !error && <Shimmer />}
        {files && (
          <FileBrowser
            files={shown}
            rootLabel={AREAS.find((a) => a.key === area)!.title}
            path={path}
            onPathChange={setPath}
            selected={value?.startsWith(`${area}/`) ? value.slice(area.length + 1) : undefined}
            onSelect={(f) => !isFolder && onChoose(`${area}/${f.name}`)}
            folderLabels={area === "results" ? runLabels : {}}
            emptyMessage={
              area === "inputs"
                ? "No matching files. Upload files on the Data page, or turn on Show all files."
                : "No matching results from earlier runs."
            }
          />
        )}
        {!isFolder && files && (
          <Text variant="small" className="nf-muted">
            Select a file to use it. Folders open when selected.
          </Text>
        )}
      </Stack>
    </Panel>
  );
};

/** Labels for run folders in Results, such as "my label · Germline demo · 5 Nov 22:21". */
export function useRunLabels(): Record<string, string> {
  const [labels, setLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    api
      .get<Run[]>("/api/runs")
      .then((runs) =>
        setLabels(
          Object.fromEntries(
            runs.map((r) => [r.id, `${r.label || r.nextflow_run_name || r.id} · ${r.pipeline_name} · ${formatShortDate(r.created_at)}`]),
          ),
        ),
      )
      .catch(() => setLabels({}));
  }, []);
  return labels;
}
