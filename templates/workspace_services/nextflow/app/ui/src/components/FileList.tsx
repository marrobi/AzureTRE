import React, { useMemo } from "react";
import {
  DetailsList,
  DetailsListLayoutMode,
  FontIcon,
  IColumn,
  Link,
  Selection,
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

interface Props {
  files: StoredFile[];
  stripPrefix?: string;
  selected?: string;
  onSelect: (file: StoredFile) => void;
  renderActions?: (file: StoredFile) => React.ReactNode;
  emptyMessage: string;
}

export const FileList: React.FunctionComponent<Props> = ({
  files,
  stripPrefix = "",
  selected,
  onSelect,
  renderActions,
  emptyMessage,
}) => {
  const selection = useMemo(() => new Selection(), []);
  const columns: IColumn[] = [
    {
      key: "name",
      name: "Name",
      minWidth: 140,
      isResizable: true,
      onRender: (f: StoredFile) => (
        <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 8 }}>
          <FontIcon iconName={KIND_ICONS[f.kind] ?? "Page"} aria-hidden />
          <Link onClick={() => onSelect(f)} className={f.name === selected ? "nf-selected" : undefined}>
            {f.name.slice(stripPrefix.length)}
          </Link>
        </Stack>
      ),
    },
    { key: "size", name: "Size", minWidth: 55, maxWidth: 80, onRender: (f: StoredFile) => formatSize(f.size) },
    {
      key: "modified",
      name: "Modified",
      minWidth: 110,
      maxWidth: 150,
      onRender: (f: StoredFile) => formatShortDate(f.last_modified),
    },
  ];
  if (renderActions) {
    columns.push({ key: "actions", name: "", minWidth: 120, onRender: renderActions });
  }
  if (!files.length) return <Text className="nf-muted">{emptyMessage}</Text>;
  return (
    <DetailsList
      items={files}
      columns={columns}
      selection={selection}
      selectionMode={SelectionMode.none}
      layoutMode={DetailsListLayoutMode.justified}
      compact
      getKey={(f: StoredFile) => f.name}
    />
  );
};
