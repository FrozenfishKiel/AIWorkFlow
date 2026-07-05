import { apiClient } from "./api";
import type { ExportJobCreateInput, ExportJobRecord } from "../types/export";

export async function createExportJob(payload: ExportJobCreateInput): Promise<ExportJobRecord> {
  return await apiClient.post<ExportJobRecord>("/exports", {
    task_id: payload.taskId,
    export_type: payload.exportType,
  });
}

export async function fetchExportJob(exportJobId: string): Promise<ExportJobRecord> {
  return await apiClient.get<ExportJobRecord>(`/exports/${exportJobId}`);
}

export async function listExportJobs(taskId: string): Promise<ExportJobRecord[]> {
  return await apiClient.get<ExportJobRecord[]>(`/exports?task_id=${encodeURIComponent(taskId)}`);
}

export async function downloadExportArtifact(exportJobId: string): Promise<Blob> {
  return await apiClient.getBlob(`/exports/${exportJobId}/artifact`);
}
