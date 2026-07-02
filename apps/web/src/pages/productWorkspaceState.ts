import { ApiError } from "../services/api";

export interface StoredJobRecoveryAction {
  clearStoredJob: boolean;
  message: string | null;
}

export function getStoredJobRecoveryAction(error: unknown): StoredJobRecoveryAction {
  if (error instanceof ApiError && (error.status === 404 || error.status === 422)) {
    return {
      clearStoredJob: true,
      message: null,
    };
  }

  return {
    clearStoredJob: false,
    message: error instanceof Error ? error.message : "加载当前结果失败。",
  };
}
