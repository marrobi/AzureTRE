import React, { useEffect, useMemo, useState } from "react";
import {
  DefaultButton,
  Dropdown,
  MessageBar,
  MessageBarType,
  PrimaryButton,
  Shimmer,
  Stack,
  Text,
  TextField,
  Toggle,
} from "@fluentui/react";
import ReactMarkdown from "react-markdown";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Card } from "../components/Card";
import { ErrorBar } from "../components/ErrorBar";
import { PathPicker, useRunLabels } from "../components/PathPicker";
import { ParamField, Pipeline, Run } from "../types";

type Values = Record<string, unknown>;

function initialValues(fields: ParamField[]): Values {
  const values: Values = {};
  for (const f of fields) {
    if (f.default !== null && f.default !== undefined) values[f.name] = f.default;
  }
  return values;
}

export const LaunchPage: React.FunctionComponent = () => {
  const { pipelineId = "" } = useParams();
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState<Pipeline>();
  const runLabels = useRunLabels();
  const [values, setValues] = useState<Values>({});
  const [label, setLabel] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get<Pipeline>(`/api/pipelines/${encodeURIComponent(pipelineId)}`)
      .then((p) => {
        setPipeline(p);
        setValues(initialValues(p.fields));
      })
      .catch((e) => setError(e.message));
  }, [pipelineId]);

  const groups = useMemo(() => {
    const result = new Map<string, ParamField[]>();
    for (const f of pipeline?.fields ?? []) {
      if (f.hidden && !showHidden) continue;
      result.set(f.group, [...(result.get(f.group) ?? []), f]);
    }
    return [...result.entries()];
  }, [pipeline, showHidden]);

  const set = (name: string, value: unknown) => setValues((v) => ({ ...v, [name]: value }));

  const submit = async () => {
    if (!pipeline) return;
    setSubmitting(true);
    setErrors({});
    setError(undefined);
    try {
      const run = await api.post<Run>("/api/runs", { pipeline_id: pipeline.id, params: values, label });
      navigate(`/runs/${run.id}`);
    } catch (e) {
      const err = e as ApiError;
      const body = err.body as { errors?: Record<string, string> } | null;
      if (err.status === 422 && body?.errors) {
        setErrors(body.errors);
        setError("Check the highlighted parameters.");
      } else {
        setError(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const renderField = (f: ParamField) => {
    const common = {
      label: f.title,
      description: f.description,
      required: f.required,
      errorMessage: errors[f.name],
    };
    const value = values[f.name];
    if (f.type === "boolean") {
      return (
        <Stack key={f.name}>
          <Toggle label={f.title} checked={Boolean(value)} onChange={(_, checked) => set(f.name, checked)} />
          {f.description && <Text variant="small" className="nf-muted">{f.description}</Text>}
          {errors[f.name] && <Text className="nf-error">{errors[f.name]}</Text>}
        </Stack>
      );
    }
    if (f.enum) {
      return (
        <Dropdown
          key={f.name}
          {...common}
          options={f.enum.map((o) => ({ key: String(o), text: String(o) }))}
          selectedKey={value === undefined ? null : String(value)}
          onChange={(_, option) =>
            set(f.name, option ? f.enum!.find((o) => String(o) === option.key) : undefined)
          }
        />
      );
    }
    if (f.is_path) {
      return (
        <PathPicker
          key={f.name}
          field={f}
          value={typeof value === "string" ? value : undefined}
          errorMessage={errors[f.name]}
          runLabels={runLabels}
          onChange={(v) => set(f.name, v)}
        />
      );
    }
    if (f.type === "integer" || f.type === "number") {
      return (
        <TextField
          key={f.name}
          {...common}
          type="number"
          min={f.minimum ?? undefined}
          max={f.maximum ?? undefined}
          step={f.type === "integer" ? 1 : "any"}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(_, v) => set(f.name, v === "" || v === undefined ? undefined : Number(v))}
        />
      );
    }
    return (
      <TextField
        key={f.name}
        {...common}
        value={value === undefined || value === null ? "" : String(value)}
        onChange={(_, v) => set(f.name, v)}
      />
    );
  };

  if (!pipeline) {
    return (
      <Stack tokens={{ childrenGap: 10 }}>
        <h1>Start a run</h1>
        <ErrorBar error={error} />
        {!error && <Shimmer />}
      </Stack>
    );
  }

  const hasHidden = pipeline.fields.some((f) => f.hidden);
  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <h1>Start a run: {pipeline.name}</h1>
      <Stack horizontal wrap tokens={{ childrenGap: 24 }}>
        <Stack className="nf-form" tokens={{ childrenGap: 16 }}>
          <Card>
            <TextField
              label="Run label"
              description="Optional. Helps you find this run later."
              value={label}
              maxLength={120}
              onChange={(_, v) => setLabel(v ?? "")}
            />
          </Card>
          {!pipeline.fields.length && (
            <MessageBar messageBarType={MessageBarType.warning}>
              This pipeline has no nextflow_schema.json, so it runs with its default parameters.
            </MessageBar>
          )}
          {groups.map(([group, fields]) => (
            <Card key={group}>
              <Text variant="large">{group}</Text>
              {fields.map(renderField)}
            </Card>
          ))}
          {hasHidden && (
            <Toggle label="Show hidden parameters" checked={showHidden} onChange={(_, c) => setShowHidden(!!c)} />
          )}
          <ErrorBar error={error} onDismiss={() => setError(undefined)} />
          <Stack horizontal tokens={{ childrenGap: 10 }}>
            <PrimaryButton text={submitting ? "Starting…" : "Start run"} disabled={submitting} onClick={submit} />
            <DefaultButton text="Cancel" onClick={() => navigate("/pipelines")} />
          </Stack>
        </Stack>
        {pipeline.readme && (
          <Card className="nf-readme">
            <div className="nf-markdown">
              <ReactMarkdown>{pipeline.readme}</ReactMarkdown>
            </div>
          </Card>
        )}
      </Stack>
    </Stack>
  );
};
