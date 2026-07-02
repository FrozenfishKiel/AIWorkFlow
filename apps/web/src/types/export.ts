export type ExportType = "markdown" | "structured_text";
export type ExportJobStatus = "queued" | "exporting" | "completed" | "failed";

export interface ExportJobRecord {
  id: string;
  task_id: string;
  export_type: ExportType;
  status: ExportJobStatus;
  file_path?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExportJobCreateInput {
  taskId: string;
  exportType: ExportType;
}
