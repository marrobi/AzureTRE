import React, { useMemo, useState } from "react";
import {
  Breadcrumb,
  DetailsList,
  DetailsListLayoutMode,
  FontIcon,
  IBreadcrumbItem,
  IColumn,
  Link,
  SearchBox,
  SelectionMode,
  Stack,
  Text,
} from "@fluentui/react";
import { formatShortDate, formatSize } from "../format";
import { StoredFile } from "../types";

const KIND_ICONS: Record<string, string> = {
  image: "FileImage",
  html: "FileHTML",
  table: "ExcelDocument",
  markdown: "MarkDownLanguage",
  pdf: "PDF",
  text: "TextDocument",
  binary: "Page",
};

interface Entry {
  key: string;
  name: string;
  folder: boolean;
  path: string;
  file?: StoredFile;
  count: number;
  size: number;
  modified: string | null;
}

export interface FileBrowserProps {
  files: StoredFile[];
  /** Prefix of every file name shown, for example "<run id>/". */
  root?: string;
  rootLabel: string;
  /** Current folder, relative to root, ending in "/" (or "" for the root). */
  path: string;
  onPathChange: (path: string) => void;
  selected?: string;
  onSelect: (file: StoredFile) => void;
  /** Folders under the root that aren't listed, such as Nextflow's own reports. */
  hiddenFolders?: string[];
  /** Friendly labels for folders at the root, such as run names for run IDs. */
  folderLabels?: Record<string, string>;
  renderActions?: (file: StoredFile) => React.ReactNode;
  emptyMessage: string;
}

function entriesFor(files: StoredFile[], root: string, path: string, hidden: string[]): Entry[] {
  const folders = new Map<string, Entry>();
  const result: Entry[] = [];
  const base = root + path;
  for (const f of files) {
    if (!f.name.startsWith(base)) continue;
    const rest = f.name.slice(base.length);
    const slash = rest.indexOf("/");
    if (slash < 0) {
      result.push({ key: f.name, name: rest, folder: false, path: f.name, file: f, count: 1, size: f.size, modified: f.last_modified });
      continue;
    }
    const name = rest.slice(0, slash);
    if (!path && hidden.includes(name)) continue;
    const entry = folders.get(name) ?? { key: `${base}${name}/`, name, folder: true, path: `${path}${name}/`, count: 0, size: 0, modified: null };
    entry.count += 1;
    entry.size += f.size;
    if (f.last_modified && (!entry.modified || f.last_modified > entry.modified)) entry.modified = f.last_modified;
    folders.set(name, entry);
  }
  const byName = (a: Entry, b: Entry) => a.name.localeCompare(b.name, undefined, { numeric: true });
  return [...[...folders.values()].sort(byName), ...result.sort(byName)];
}

export const FileBrowser: React.FunctionComponent<FileBrowserProps> = ({
  files,
  root = "",
  rootLabel,
  path,
  onPathChange,
  selected,
  onSelect,
  hiddenFolders = [],
  folderLabels = {},
  renderActions,
  emptyMessage,
}) => {
  const [filter, setFilter] = useState("");

  const entries = useMemo(() => {
    if (!filter) return entriesFor(files, root, path, hiddenFolders);
    const needle = filter.toLowerCase();
    return files
      .filter((f) => f.name.startsWith(root) && f.name.slice(root.length).toLowerCase().includes(needle))
      .filter((f) => !hiddenFolders.some((h) => f.name.startsWith(`${root}${h}/`)))
      .map<Entry>((f) => ({ key: f.name, name: f.name.slice(root.length), folder: false, path: f.name, file: f, count: 1, size: f.size, modified: f.last_modified }));
  }, [files, root, path, hiddenFolders, filter]);

  const crumbs: IBreadcrumbItem[] = [{ key: "", text: rootLabel, onClick: () => onPathChange("") }];
  let acc = "";
  for (const part of path.split("/").filter(Boolean)) {
    acc += `${part}/`;
    const target = acc;
    crumbs.push({ key: target, text: (crumbs.length === 1 && folderLabels[part]) || part, onClick: () => onPathChange(target) });
  }
  crumbs[crumbs.length - 1] = { ...crumbs[crumbs.length - 1], onClick: undefined, isCurrentItem: true };

  const open = (e: Entry) => (e.folder ? onPathChange(e.path) : e.file && onSelect(e.file));

  const columns: IColumn[] = [
    {
      key: "name",
      name: "Name",
      minWidth: 150,
      isResizable: true,
      onRender: (e: Entry) => {
        const label = e.folder && !path && folderLabels[e.name];
        const detail = label ? e.name : e.folder ? `${e.count} file${e.count === 1 ? "" : "s"}` : "";
        return (
          <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 8 }}>
            <FontIcon
              iconName={e.folder ? "FabricFolderFill" : KIND_ICONS[e.file?.kind ?? "binary"] ?? "Page"}
              className={e.folder ? "nf-folder-icon" : undefined}
              aria-hidden
            />
            <Stack>
              <Link onClick={() => open(e)} className={e.path === selected ? "nf-selected" : undefined}>
                {label || e.name}
              </Link>
              {detail && <Text variant="small" className="nf-muted">{detail}</Text>}
            </Stack>
          </Stack>
        );
      },
    },
    {
      key: "size",
      name: "Size",
      minWidth: 60,
      maxWidth: 80,
      onRender: (e: Entry) => formatSize(e.size),
    },
    { key: "modified", name: "Modified", minWidth: 100, maxWidth: 130, onRender: (e: Entry) => formatShortDate(e.modified) },
  ];
  if (renderActions) {
    columns.push({ key: "actions", name: "", minWidth: 110, onRender: (e: Entry) => (e.file ? renderActions(e.file) : null) });
  }

  return (
    <Stack tokens={{ childrenGap: 6 }}>
      <SearchBox
        placeholder="Search all folders"
        value={filter}
        onChange={(_, v) => setFilter(v ?? "")}
        className="nf-search"
      />
      {!filter && (
        <Breadcrumb items={crumbs} maxDisplayedItems={6} overflowIndex={0} className="nf-breadcrumb" ariaLabel="Folder" />
      )}
      {entries.length === 0 ? (
        <Text className="nf-muted">{filter ? "No files match the search." : emptyMessage}</Text>
      ) : (
        <DetailsList
          items={entries}
          columns={columns}
          selectionMode={SelectionMode.none}
          layoutMode={DetailsListLayoutMode.justified}
          compact
          getKey={(e: Entry) => e.key}
          onItemInvoked={open}
        />
      )}
    </Stack>
  );
};

/** Reports and summaries worth opening first, anywhere in a run's results. */
export function keyOutputs(files: StoredFile[], root: string): StoredFile[] {
  const score = (f: StoredFile) => {
    const name = f.name.slice(root.length);
    const depth = name.split("/").length - 1;
    const base = name.split("/").pop() ?? "";
    if (base === "report.html" && depth === 0) return 11;
    if (f.kind === "html" && /report/i.test(base)) return 10 - depth;
    if (f.kind === "html" && depth === 0) return 8;
    if (base === "README.md" && depth === 0) return 7;
    if ((f.kind === "pdf" || f.kind === "image") && depth === 0) return 6;
    if (f.kind === "table" && depth === 0) return 5;
    return 0;
  };
  return files
    .filter((f) => f.name.startsWith(root) && !f.name.startsWith(`${root}_nextflow/`) && score(f) > 0)
    .sort((a, b) => score(b) - score(a) || a.name.localeCompare(b.name))
    .slice(0, 6);
}
