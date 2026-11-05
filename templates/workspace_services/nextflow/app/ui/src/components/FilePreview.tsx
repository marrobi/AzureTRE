import React, { useEffect, useState } from "react";
import {
  DetailsList,
  DetailsListLayoutMode,
  IColumn,
  Link,
  MessageBar,
  SelectionMode,
  Spinner,
  Stack,
  Text,
} from "@fluentui/react";
import ReactMarkdown from "react-markdown";
import { api, fileUrl } from "../api";
import { Preview } from "../types";
import { ErrorBar } from "./ErrorBar";

interface Props {
  container: string;
  name: string;
  label?: string;
}

export const FilePreview: React.FunctionComponent<Props> = ({ container, name, label }) => {
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    setPreview(undefined);
    setError(undefined);
    api
      .get<Preview>(`/api/storage/${container}/preview?name=${encodeURIComponent(name)}`)
      .then(setPreview)
      .catch((e) => setError(e.message));
  }, [container, name]);

  const url = fileUrl(container, name);
  return (
    <Stack tokens={{ childrenGap: 10 }} className="nf-preview">
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center" wrap>
        <Text variant="large" className="nf-break">
          {label ?? name}
        </Text>
        <Stack horizontal tokens={{ childrenGap: 16 }}>
          <Link href={url} target="_blank" rel="noopener">
            Open in new tab
          </Link>
          <Link href={fileUrl(container, name, true)}>Download</Link>
        </Stack>
      </Stack>
      <ErrorBar error={error} />
      {!preview && !error && <Spinner label="Loading preview" />}
      {preview && <PreviewBody preview={preview} />}
    </Stack>
  );
};

const PreviewBody: React.FunctionComponent<{ preview: Preview }> = ({ preview }) => {
  const truncated = preview.truncated && (
    <MessageBar>Only the start of this file is shown. Download it to see everything.</MessageBar>
  );
  switch (preview.kind) {
    case "image":
      return <img src={preview.url} alt={preview.name} className="nf-image" />;
    case "html":
      // Reports run scripts in an opaque origin; the file response also carries a CSP sandbox.
      return <iframe src={preview.url} title={preview.name} sandbox="allow-scripts" className="nf-frame" />;
    case "pdf":
      return <iframe src={preview.url} title={preview.name} className="nf-frame" />;
    case "table": {
      const columns: IColumn[] = (preview.columns ?? []).map((c) => ({
        key: c,
        name: c,
        fieldName: c,
        minWidth: 60,
        maxWidth: 220,
        isResizable: true,
      }));
      return (
        <>
          {truncated}
          <div className="nf-table-scroll">
            <DetailsList
              items={preview.rows ?? []}
              columns={columns}
              selectionMode={SelectionMode.none}
              layoutMode={DetailsListLayoutMode.fixedColumns}
              compact
            />
          </div>
        </>
      );
    }
    case "markdown":
      return (
        <>
          {truncated}
          <div className="nf-markdown">
            <ReactMarkdown>{preview.text ?? ""}</ReactMarkdown>
          </div>
        </>
      );
    case "text":
      return (
        <>
          {truncated}
          <pre className="nf-pre">{preview.text}</pre>
        </>
      );
    default:
      return <MessageBar>No preview is available for this file type. Download it to open it.</MessageBar>;
  }
};
