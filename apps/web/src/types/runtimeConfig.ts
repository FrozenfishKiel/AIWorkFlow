export interface RuntimeConfig {
  env_file_path: string;
  setup_required: boolean;
  deepseek_configured: boolean;
  deepseek_api_base_url: string;
  deepseek_model: string;
  task_generation_provider: string;
  retrieval_profile_provider: string;
  missing_required_settings: string[];
}

export interface RuntimeConfigUpdateInput {
  deepseek_api_key: string;
  deepseek_api_base_url?: string;
  deepseek_model?: string;
}
