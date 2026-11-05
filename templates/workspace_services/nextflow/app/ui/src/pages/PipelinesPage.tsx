import React, { useEffect, useState } from "react";
import { MessageBar, PrimaryButton, Shimmer, Stack, Text } from "@fluentui/react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { PipelineSummary } from "../types";

export const PipelinesPage: React.FunctionComponent = () => {
  const navigate = useNavigate();
  const [pipelines, setPipelines] = useState<PipelineSummary[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api
      .get<PipelineSummary[]>("/api/pipelines")
      .then(setPipelines)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <h1>Pipelines</h1>
      <MessageBar>
        To add a pipeline, upload its folder to <b>Pipelines</b> on the Data page. The folder needs a{" "}
        <code>main.nf</code>, and a <code>nextflow_schema.json</code> to generate the launch form. Every process must
        set a <code>container</code>; the workspace can only pull Docker Hub images through the TRE Nexus proxy.
      </MessageBar>
      <ErrorBar error={error} />
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
