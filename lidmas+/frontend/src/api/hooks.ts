import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type {
  AuthSessionResponse,
  AuthSignInRequest,
  AuthSignOutResponse,
  AuthSignUpRequest,
  CompleteHardwareSessionResponse,
  CreateHardwareSessionRequest,
  CreateHardwareSessionResponse,
  AuthUserProfile,
  CreateJobRequest,
  CreateProviderRequest,
  CreateRunRequest,
  HealthResponse,
  HardwareApiSchemaResponse,
  HardwareSession,
  IngestHardwareFramesRequest,
  IngestHardwareFramesResponse,
  IntegrationSession,
  IntegrationSessionLogsResponse,
  Job,
  Paper04Manifest,
  Provider,
  RunPaper04Request,
  RunPaper04Response,
  Run,
  RunTelemetry,
  SetIbmApiKeyRequest,
  SetIbmApiKeyResponse,
  VendorCalibrationRefreshResponse,
  VendorCalibrationsCatalogResponse,
  StartIntegrationSessionRequest,
  StopIntegrationSessionResponse,
  SystemLogScanRequest,
  SystemLogScanResponse,
  UpsertRunTelemetryRequest,
  ValidationReport,
} from "./types";

interface QueryHookOptions {
  enabled?: boolean;
  refetchInterval?: number;
}

interface HealthQueryHookOptions extends QueryHookOptions {}

interface PollingQueryHookOptions extends QueryHookOptions {}

interface RunTelemetryQueryHookOptions extends QueryHookOptions {
  scientificMode?: boolean;
}

export function useHealth(options?: HealthQueryHookOptions) {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/health"),
    refetchInterval: options?.refetchInterval ?? 5000,
    enabled: options?.enabled ?? true,
  });
}

export function useSignUp() {
  return useMutation({
    mutationFn: (payload: AuthSignUpRequest) =>
      apiFetch<AuthSessionResponse>("/auth/signup", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useSignIn() {
  return useMutation({
    mutationFn: (payload: AuthSignInRequest) =>
      apiFetch<AuthSessionResponse>("/auth/signin", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useAuthMe(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["auth-me"],
    queryFn: () => apiFetch<AuthUserProfile>("/auth/me"),
    enabled: options?.enabled ?? true,
    retry: false,
  });
}

export function useSignOut() {
  return useMutation({
    mutationFn: () =>
      apiFetch<AuthSignOutResponse>("/auth/signout", {
        method: "POST",
        body: JSON.stringify({}),
      }),
  });
}

export function useProviders(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => apiFetch<Provider[]>("/providers"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateProviderRequest) =>
      apiFetch<Provider>("/providers", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["providers"] });
    },
  });
}

export function useJobs(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiFetch<Job[]>("/jobs"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateJobRequest) =>
      apiFetch<Job>("/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useRuns(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => apiFetch<Run[]>("/runs"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateRunRequest) =>
      apiFetch<Run>("/runs", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useRunTelemetry(runId: string | null, options?: RunTelemetryQueryHookOptions) {
  const scientificParam = options?.scientificMode ? "?scientific=true" : "";
  return useQuery({
    queryKey: ["run-telemetry", runId, scientificParam],
    queryFn: () => apiFetch<RunTelemetry>(`/runs/${runId}/telemetry${scientificParam}`),
    enabled: Boolean(runId) && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
  });
}

export function useUpsertRunTelemetry(runId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpsertRunTelemetryRequest) => {
      if (!runId) {
        throw new Error("runId is required");
      }
      return apiFetch<RunTelemetry>(`/runs/${runId}/telemetry`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async (_, __, ___) => {
      if (runId) {
        await qc.invalidateQueries({ queryKey: ["run-telemetry", runId] });
      }
      await qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useHardwareSchema(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["hardware-schema"],
    queryFn: () => apiFetch<HardwareApiSchemaResponse>("/hardware/schema"),
    enabled: options?.enabled ?? true,
  });
}

export function useHardwareSessions(options?: PollingQueryHookOptions) {
  return useQuery({
    queryKey: ["hardware-sessions"],
    queryFn: () => apiFetch<HardwareSession[]>("/hardware/sessions"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval ?? 3000,
  });
}

export function useCreateHardwareSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateHardwareSessionRequest) =>
      apiFetch<CreateHardwareSessionResponse>("/hardware/sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["hardware-sessions"] });
      await qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

interface IngestHardwareFramesMutationPayload {
  sessionId: string;
  payload: IngestHardwareFramesRequest;
}

export function useIngestHardwareFrames() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, payload }: IngestHardwareFramesMutationPayload) =>
      apiFetch<IngestHardwareFramesResponse>(`/hardware/sessions/${sessionId}/frames`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async (response) => {
      await qc.invalidateQueries({ queryKey: ["hardware-sessions"] });
      await qc.invalidateQueries({ queryKey: ["run-telemetry", response.telemetry.run_id] });
      await qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useCompleteHardwareSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<CompleteHardwareSessionResponse>(`/hardware/sessions/${sessionId}/complete`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: async (response) => {
      await qc.invalidateQueries({ queryKey: ["hardware-sessions"] });
      await qc.invalidateQueries({ queryKey: ["runs"] });
      if (response.telemetry?.run_id) {
        await qc.invalidateQueries({ queryKey: ["run-telemetry", response.telemetry.run_id] });
      }
    },
  });
}

export interface ValidatePayload {
  providerId: string;
  dataset_label: string;
  request_lines: number;
  response_lines: number;
  request_parse_errors: number;
  response_parse_errors: number;
  decoder_name_mismatch_count: number;
  warning_no_syndrome_count?: number;
}

export function useValidateProviderOutput() {
  return useMutation({
    mutationFn: (payload: ValidatePayload) => {
      const { providerId, ...body } = payload;
      return apiFetch<ValidationReport>(`/providers/${providerId}/validate`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  });
}

export function useSystemLogScan() {
  return useMutation({
    mutationFn: (payload: SystemLogScanRequest) =>
      apiFetch<SystemLogScanResponse>("/system/logscan", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useSetIbmApiKey() {
  return useMutation({
    mutationFn: (payload: SetIbmApiKeyRequest) =>
      apiFetch<SetIbmApiKeyResponse>("/system/credentials/ibm", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useVendorCalibrations(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["vendor-calibrations"],
    queryFn: () => apiFetch<VendorCalibrationsCatalogResponse>("/system/calibrations"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
    retry: false,
  });
}

export function useRefreshVendorCalibrations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<VendorCalibrationRefreshResponse>("/system/calibrations/refresh", {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["vendor-calibrations"] });
    },
  });
}

export function usePaper04Manifest(options?: QueryHookOptions) {
  return useQuery({
    queryKey: ["paper-04-manifest"],
    queryFn: () => apiFetch<Paper04Manifest>("/system/paper_04/manifest"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
    retry: false,
  });
}

export function useRunPaper04() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RunPaper04Request) =>
      apiFetch<RunPaper04Response>("/system/paper_04/run", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["paper-04-manifest"] });
      await qc.invalidateQueries({ queryKey: ["runs"] });
      await qc.invalidateQueries({ queryKey: ["integration-sessions"] });
    },
  });
}

export function useIntegrationSessions(options?: PollingQueryHookOptions) {
  return useQuery({
    queryKey: ["integration-sessions"],
    queryFn: () => apiFetch<IntegrationSession[]>("/integrations/sessions"),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval ?? 3000,
    retry: false,
  });
}

export function useCreateIntegrationSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartIntegrationSessionRequest) =>
      apiFetch<IntegrationSession>("/integrations/sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["integration-sessions"] });
    },
  });
}

export function useStopIntegrationSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<StopIntegrationSessionResponse>(`/integrations/sessions/${sessionId}/stop`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["integration-sessions"] });
    },
  });
}

export function useIntegrationSessionLogs(
  sessionId: string | null,
  tail: number,
  options?: PollingQueryHookOptions,
) {
  return useQuery({
    queryKey: ["integration-session-logs", sessionId, tail],
    queryFn: () =>
      apiFetch<IntegrationSessionLogsResponse>(
        `/integrations/sessions/${sessionId}/logs?tail=${encodeURIComponent(tail)}`,
    ),
    enabled: Boolean(sessionId) && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval ?? 2000,
    retry: false,
  });
}
