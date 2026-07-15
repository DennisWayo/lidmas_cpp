export interface HealthResponse {
  status: string;
  version: string;
  started_at: string;
  uptime_seconds: number;
}

export interface AuthUserProfile {
  id: string;
  full_name: string;
  email: string;
  created_at: string;
}

export interface AuthSignUpRequest {
  full_name: string;
  email: string;
  password: string;
}

export interface AuthSignInRequest {
  email: string;
  password: string;
}

export interface AuthSessionResponse {
  token: string;
  token_type: string;
  expires_at: string;
  user: AuthUserProfile;
}

export interface AuthSignOutResponse {
  signed_out: boolean;
  message: string;
}

export type ProviderKind =
  | "photonic"
  | "superconducting"
  | "trapped_ion"
  | "simulated"
  | "other";

export type ProviderStatus = "ready" | "degraded" | "offline";

export interface Provider {
  id: string;
  name: string;
  status: ProviderStatus;
  kind: ProviderKind;
  hardware_kind: ProviderKind;
  contact_email?: string | null;
  supported_formats: string[];
  supports_scientific: boolean;
  supports_benchmark: boolean;
  supports_replay: boolean;
  supports_live: boolean;
  last_seen?: string | null;
  readiness_note?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateProviderRequest {
  name: string;
  kind: ProviderKind;
  status?: ProviderStatus;
  contact_email?: string;
  supported_formats: string[];
  supports_scientific?: boolean;
  supports_benchmark?: boolean;
  supports_replay?: boolean;
  supports_live?: boolean;
  readiness_note?: string;
  notes?: string;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  provider_id: string;
  dataset_label: string;
  decoders: string[];
  priority: number;
  status: JobStatus;
  message?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface CreateJobRequest {
  provider_id: string;
  dataset_label: string;
  decoders: string[];
  priority?: number;
}

export type RunStatus = "created" | "running" | "finished" | "failed" | "cancelled";

export interface RunArtifact {
  name: string;
  kind: string;
  path: string;
  sha256?: string | null;
  created_at: string;
}

export interface RunDecoderRanking {
  decoder: string;
  logical_error_rate: number;
  avg_flips: number;
  residual_nonzero_rate: number;
  correction_efficiency: number;
}

export interface DecoderExactTelemetry {
  decoder: string;
  trials: number;
  logical_failures: number;
  encoder_state?: string | null;
}

export interface RunMetrics {
  avg_flip_count?: number | null;
  nonempty_flip_rate?: number | null;
  syndrome_satisfaction_rate?: number | null;
  residual_nonzero_rate?: number | null;
  warning_rate?: number | null;
  physical_error_rate?: number | null;
  baseline_logical_error_rate?: number | null;
  logical_error_rate?: number | null;
  logical_failures?: number | null;
  logical_trials?: number | null;
  physical_error_events?: number | null;
  physical_error_opportunities?: number | null;
  request_line_count?: number | null;
  response_line_count?: number | null;
  rounds?: number | null;
  stabilizer_count?: number | null;
  syndrome_opportunities?: number | null;
  residual_syndrome_events?: number | null;
  expanded_shot_count?: number | null;
  decoder_exact_metrics?: DecoderExactTelemetry[] | null;
  ler_per_gate_triggered?: boolean | null;
  ler_per_gate_passed?: boolean | null;
  logical_error_rate_source?: string | null;
  scientific_validation_ready?: boolean | null;
  best_decoder?: string | null;
  best_encoder_state?: string | null;
  decoder_rankings?: RunDecoderRanking[] | null;
}

export interface Run {
  id: string;
  job_id?: string | null;
  workflow_id?: string | null;
  provider_id: string;
  dataset_label: string;
  decoders: string[];
  status: RunStatus;
  message?: string | null;
  artifacts: RunArtifact[];
  metrics?: RunMetrics | null;
  created_at: string;
  updated_at: string;
}

export interface CreateRunRequest {
  job_id?: string;
  workflow_id?: string;
  provider_id?: string;
  dataset_label?: string;
  decoders?: string[];
}

export interface ValidationReport {
  provider_id: string;
  dataset_label: string;
  line_coverage_ok: boolean;
  parse_integrity_ok: boolean;
  decoder_name_integrity_ok: boolean;
  warning_rate?: number | null;
  overall_ok: boolean;
  checks: string[];
  checked_at: string;
}

export interface NoiseSample {
  index: number;
  physical_error_rate: number;
  displacement_sigma: number;
  photon_loss_rate: number;
}

export interface SyndromeSample {
  round: number;
  stabilizer: string;
  value: number;
  is_triggered: boolean;
}

export interface GkpOscillatorStateSample {
  round: number;
  mode: string;
  q: number;
  p: number;
  variance?: number | null;
  energy?: number | null;
  flagged?: boolean;
}

export interface DecoderIntervention {
  decoder: string;
  round: number;
  flips: number;
  residual_weight: number;
}

export interface RunTelemetry {
  run_id: string;
  // Legacy overloaded counter; scientific mode should prefer explicit line/shot counters below.
  request_count: number;
  request_line_count?: number | null;
  response_line_count?: number | null;
  response_ratio?: number | null;
  expanded_shot_count?: number | null;
  rounds: number;
  stabilizer_count: number;
  syndrome_opportunities?: number | null;
  decoder_name?: string | null;
  logical_failures?: number | null;
  logical_trials?: number | null;
  logical_error_rate?: number | null;
  physical_error_events?: number | null;
  physical_error_opportunities?: number | null;
  physical_error_rate?: number | null;
  residual_syndrome_events?: number | null;
  residual_syndrome_rate?: number | null;
  warning_rate?: number | null;
  noise_samples: NoiseSample[];
  syndrome_samples: SyndromeSample[];
  decoder_exact_metrics?: DecoderExactTelemetry[] | null;
  gkp_oscillator_states?: GkpOscillatorStateSample[];
  decoder_interventions: DecoderIntervention[];
  updated_at: string;
}

export interface UpsertRunTelemetryRequest {
  request_count?: number;
  request_line_count?: number;
  response_line_count?: number;
  response_ratio?: number;
  expanded_shot_count?: number;
  rounds?: number;
  stabilizer_count?: number;
  syndrome_opportunities?: number;
  decoder_name?: string;
  logical_failures?: number;
  logical_trials?: number;
  logical_error_rate?: number;
  physical_error_events?: number;
  physical_error_opportunities?: number;
  physical_error_rate?: number;
  residual_syndrome_events?: number;
  residual_syndrome_rate?: number;
  warning_rate?: number;
  noise_samples: NoiseSample[];
  syndrome_samples: SyndromeSample[];
  decoder_exact_metrics?: DecoderExactTelemetry[];
  gkp_oscillator_states?: GkpOscillatorStateSample[];
  decoder_interventions: DecoderIntervention[];
}

export type HardwareSourceMode = "live" | "replay";
export type HardwareSessionStatus = "active" | "completed" | "failed" | "cancelled";

export interface HardwareSession {
  id: string;
  run_id: string;
  provider_id: string;
  dataset_label: string;
  source_name: string;
  source_mode: HardwareSourceMode;
  schema_version: string;
  decoders: string[];
  status: HardwareSessionStatus;
  frame_count: number;
  started_at: string;
  updated_at: string;
  last_frame_at?: string | null;
  completed_at?: string | null;
  last_error?: string | null;
}

export interface CreateHardwareSessionRequest {
  provider_id: string;
  dataset_label: string;
  decoders: string[];
  source_name: string;
  source_mode?: HardwareSourceMode;
  schema_version?: string;
}

export interface CreateHardwareSessionResponse {
  session: HardwareSession;
  run: Run;
  frame_ingest_path: string;
  complete_path: string;
}

export interface HardwareNoiseSampleInput {
  index?: number;
  physical_error_rate: number;
  displacement_sigma: number;
  photon_loss_rate: number;
}

export interface HardwareFrameInput {
  frame_index: number;
  timestamp?: string;
  source?: string;
  backend_name?: string;
  warning_rate?: number;
  noise_sample: HardwareNoiseSampleInput;
  syndrome_samples: SyndromeSample[];
  decoder_interventions: DecoderIntervention[];
}

export interface IngestHardwareFramesRequest {
  frames: HardwareFrameInput[];
}

export interface IngestHardwareFramesResponse {
  session: HardwareSession;
  telemetry: RunTelemetry;
  ingested_frames: number;
}

export interface CompleteHardwareSessionResponse {
  session: HardwareSession;
  run: Run;
  telemetry?: RunTelemetry | null;
}

export interface HardwareApiSchemaResponse {
  schema_version: string;
  frame_format: string;
  notes: string[];
  create_session_request_example: Record<string, unknown>;
  frame_request_example: Record<string, unknown>;
}

export type IntegrationProvider =
  | "ibm"
  | "ankaa"
  | "xanadu"
  | "pennylane"
  | "qiskit"
  | "cirq";
export type IntegrationMode = "live" | "replay_static";
export type IntegrationAdapterId =
  | "ibm_superconducting_live"
  | "ankaa_superconducting_replay"
  | "xanadu_gkp_remote_replay"
  | "pennylane_surface_replay"
  | "qiskit_surface_replay"
  | "cirq_surface_replay";
export type IntegrationSessionStatus = "starting" | "running" | "finished" | "failed" | "cancelled";
export type IntegrationLogStream = "stdout" | "stderr" | "system";

export interface IntegrationSessionConfig {
  mode?: "scientific" | "benchmark" | "replay";
  provider_scope?: string;
  time_range?: string;
  run_source?: string;
  compare_decoders?: string[];
  backend_name?: string;
  ibm_live_source_mode?: "metadata" | "qpu";
  ibm_instance?: string;
  ibm_shots?: number;
  poll_interval?: number;
  max_polls?: number;
  input_path?: string;
  max_rounds?: number;
  remote?: string;
  remote_repo?: string;
  remote_python?: string;
  remote_input_root?: string;
  neural_model_path?: string;
  skip_replay?: boolean;
  simulator_code_family?: "surface" | "gkp";
  simulator_shots?: number;
  simulator_distance?: number;
  simulator_rounds?: number;
  simulator_error_rate?: number;
  simulator_sigma?: number;
  simulator_seed?: number;
  circuit_name?: string;
  circuit_qasm?: string;
  circuit_qubits?: number;
  circuit_depth?: number;
  circuit_gate_count?: number;
  circuit_hardware_target?: "superconducting" | "trapped_ion" | "photonic";
  circuit_detector_model?: "threshold" | "pnr_approx";
  circuit_noise_config?: string;
  circuit_compile_artifact?: string;
  circuit_calibration_snapshot?: string;
  circuit_gate_plan?: string;
}

export interface IntegrationSession {
  id: string;
  run_id: string;
  provider: IntegrationProvider;
  mode: IntegrationMode;
  adapter_id: IntegrationAdapterId;
  status: IntegrationSessionStatus;
  config: IntegrationSessionConfig;
  started_at: string;
  updated_at: string;
  ended_at?: string | null;
  exit_code?: number | null;
  last_error?: string | null;
}

export interface StartIntegrationSessionRequest {
  run_id: string;
  adapter_id: IntegrationAdapterId;
  config?: IntegrationSessionConfig;
}

export interface StopIntegrationSessionResponse {
  session: IntegrationSession;
  stopped: boolean;
  message: string;
}

export interface IntegrationSessionLogLine {
  timestamp: string;
  stream: IntegrationLogStream;
  line: string;
}

export interface IntegrationSessionLogsResponse {
  session_id: string;
  total_lines: number;
  has_more: boolean;
  lines: IntegrationSessionLogLine[];
}

export type LogSeverity = "critical" | "high" | "medium" | "low" | "info";
export type LogScanField = "any" | "message" | "source" | "level";
export type LogScanVerdict = "pass" | "warn" | "critical";

export interface SystemLogEntry {
  timestamp?: string | null;
  level?: string | null;
  message: string;
  source?: string | null;
}

export interface SystemLogScanRule {
  id: string;
  title: string;
  pattern: string;
  severity: LogSeverity;
  confidence?: number;
  field?: LogScanField;
  tags?: string[];
  recommendation?: string;
}

export interface SystemLogSuppression {
  pattern: string;
  field?: LogScanField;
}

export interface SystemLogScanRequest {
  logs: SystemLogEntry[];
  custom_rules?: SystemLogScanRule[];
  suppressions?: SystemLogSuppression[];
  max_findings?: number;
}

export interface SystemLogScanFinding {
  rule_id: string;
  rule_origin: string;
  title: string;
  severity: LogSeverity;
  confidence: number;
  line_index: number;
  timestamp?: string | null;
  level?: string | null;
  source?: string | null;
  message: string;
  tags: string[];
  recommendation?: string | null;
}

export interface SystemLogScanSummary {
  scanned_entries: number;
  matched_entries: number;
  suppressed_matches: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  risk_score: number;
  verdict: LogScanVerdict;
}

export interface SystemLogScanResponse {
  scan_id: string;
  summary: SystemLogScanSummary;
  findings: SystemLogScanFinding[];
  top_recommendations: string[];
  generated_at: string;
}

export interface SetIbmApiKeyRequest {
  api_key: string;
}

export interface SetIbmApiKeyResponse {
  stored: boolean;
  message: string;
  updated_at: string;
}

export interface VendorCalibrationSnapshot {
  id: string;
  label: string;
  vendor: string;
  hardware_target: string;
  backend: string;
  captured_at: string;
  source: string;
  metrics: Record<string, number>;
}

export interface VendorCalibrationsCatalogResponse {
  schema_version?: string;
  generated_at?: string;
  refresh_mode?: string;
  snapshots?: VendorCalibrationSnapshot[];
  notes?: string[];
}

export interface VendorCalibrationRefreshResponse {
  ok: boolean;
  command: string;
  duration_ms: number;
  exit_code?: number | null;
  stdout_tail: string[];
  stderr_tail: string[];
  catalog_path: string;
  refreshed_at: string;
  catalog?: VendorCalibrationsCatalogResponse;
}

export interface Paper04ArtifactDigest {
  path: string;
  exists: boolean;
  size_bytes?: number | null;
  sha256?: string | null;
}

export interface Paper04Manifest {
  generated_at: string;
  results_root: string;
  artifact_count: number;
  manifest_hash: string;
  artifacts: Paper04ArtifactDigest[];
}

export interface Paper04ParityResult {
  expected_manifest_hash: string;
  actual_manifest_hash: string;
  match_exact: boolean;
}

export interface RunPaper04Request {
  strict_three_stack?: boolean;
  enable_param_sweeps?: boolean;
  timeout_seconds?: number;
  env_overrides?: Record<string, string>;
  compare_with_manifest_hash?: string;
}

export interface RunPaper04Response {
  ok: boolean;
  status: string;
  command: string;
  duration_ms: number;
  timeout_seconds: number;
  exit_code?: number | null;
  stdout_tail: string[];
  stderr_tail: string[];
  manifest: Paper04Manifest;
  parity?: Paper04ParityResult | null;
}
