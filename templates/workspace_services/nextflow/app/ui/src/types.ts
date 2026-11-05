export interface Me {
  name: string;
  roles: string[];
  is_owner: boolean;
  service_name: string;
  max_upload_bytes: number;
}

export interface PipelineSummary {
  id: string;
  name: string;
  source: "builtin" | "storage";
  description: string;
}

export interface ParamField {
  name: string;
  type: string;
  title: string;
  description: string;
  default: unknown;
  required: boolean;
  enum: unknown[] | null;
  format: string | null;
  group: string;
  hidden: boolean;
  pattern: string | null;
  minimum: number | null;
  maximum: number | null;
  is_path: boolean;
}

export interface Pipeline extends PipelineSummary {
  readme: string;
  fields: ParamField[];
}

export interface ProcessProgress {
  name: string;
  submitted: number;
  running: number;
  succeeded: number;
  failed: number;
  cached: number;
}

export interface Run {
  id: string;
  pipeline_id: string;
  pipeline_name: string;
  params: Record<string, unknown>;
  created_by: string;
  created_by_name: string;
  created_at: string;
  status: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  error: string | null;
  nextflow_run_name: string | null;
  cancel_requested_by: string | null;
  label: string;
  progress?: ProcessProgress[];
}

export interface StoredFile {
  name: string;
  size: number;
  last_modified: string | null;
  kind: string;
}

export interface Preview {
  name: string;
  kind: string;
  url: string;
  text?: string;
  columns?: string[];
  rows?: Record<string, string>[];
  truncated?: boolean;
}

export const TERMINAL_STATUSES = ["succeeded", "failed", "cancelled"];
