import { apiClient } from "./api";
import type { RuntimeConfig, RuntimeConfigUpdateInput } from "../types/runtimeConfig";

export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  return await apiClient.get<RuntimeConfig>("/runtime-config");
}

export async function updateRuntimeConfig(payload: RuntimeConfigUpdateInput): Promise<RuntimeConfig> {
  return await apiClient.put<RuntimeConfig>("/runtime-config", payload);
}
