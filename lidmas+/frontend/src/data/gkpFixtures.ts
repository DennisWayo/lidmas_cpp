import type {
  DecoderIntervention,
  GkpOscillatorStateSample,
  HealthResponse,
  Job,
  JobStatus,
  NoiseSample,
  Provider,
  Run,
  RunStatus,
  RunTelemetry,
  SyndromeSample,
} from "../api/types";

export const GKP_SCENARIO_NAME = "GKP Surface-Lattice Benchmark";

export interface GkpProviderRuntime {
  id: string;
  name: string;
  status: "online" | "busy" | "offline";
  health: number;
  jobs: number;
  latency: string;
  throughput: string;
  successRate: string;
  lastSeen: string;
  type: string;
  region: string;
}

export interface GkpJobRuntime {
  id: string;
  name: string;
  status: "Completed" | "Running" | "Pending" | "Failed";
  progress: number;
  provider: string;
  duration: string;
  runs: string;
  successRate: string;
  created: string;
}

export interface GkpLogEntry {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "SUCCESS";
  message: string;
  source: string;
}

export interface GkpAlertItem {
  id: number;
  title: string;
  level: "critical" | "warning" | "info";
  message: string;
  triggered: string;
  meta: string;
}

export interface GkpAlertRule {
  id: number;
  name: string;
  condition: string;
  enabled: boolean;
}

const ISO_BASE = "2026-04-20T10:00:00Z";
const RUN_ID = "7f08982d-6bfb-4c64-bec8-feb4e8b2665f";

export const gkpHealth: HealthResponse = {
  status: "ok",
  version: "0.1.0",
  started_at: ISO_BASE,
  uptime_seconds: 3_920_400,
};

export const gkpProviderRuntime: GkpProviderRuntime[] = [
  {
    id: "2fb9d977-b44f-4907-8826-82f7953ac26a",
    name: "Provider-01",
    status: "online",
    health: 96,
    jobs: 8,
    latency: "42ms",
    throughput: "450 ops/s",
    successRate: "98.2%",
    lastSeen: "2 min ago",
    type: "Photonic GKP",
    region: "eu-central-1",
  },
  {
    id: "93a9edc8-1e87-4af0-9f70-3bcf56261379",
    name: "Provider-02",
    status: "online",
    health: 93,
    jobs: 6,
    latency: "48ms",
    throughput: "420 ops/s",
    successRate: "97.5%",
    lastSeen: "1 min ago",
    type: "Superconducting",
    region: "us-east-1",
  },
  {
    id: "e7fe27f7-4f0e-4992-95dc-a2f33cd9705f",
    name: "Provider-03",
    status: "busy",
    health: 88,
    jobs: 12,
    latency: "65ms",
    throughput: "380 ops/s",
    successRate: "95.2%",
    lastSeen: "30 sec ago",
    type: "Trapped Ion",
    region: "us-west-2",
  },
  {
    id: "4afcd5b2-f17c-49c4-9f3e-a68e7c6cf75b",
    name: "Provider-04",
    status: "online",
    health: 95,
    jobs: 7,
    latency: "44ms",
    throughput: "440 ops/s",
    successRate: "97.8%",
    lastSeen: "3 min ago",
    type: "Simulated GKP",
    region: "on-prem",
  },
];

export const gkpProviders: Provider[] = gkpProviderRuntime.map((provider) => ({
  id: provider.id,
  name: provider.name,
  status: provider.status === "offline" ? "offline" : provider.status === "busy" ? "degraded" : "ready",
  kind:
    provider.type.includes("Photonic")
      ? "photonic"
      : provider.type.includes("Trapped")
        ? "trapped_ion"
        : provider.type.includes("Superconducting")
          ? "superconducting"
          : "simulated",
  hardware_kind:
    provider.type.includes("Photonic")
      ? "photonic"
      : provider.type.includes("Trapped")
        ? "trapped_ion"
        : provider.type.includes("Superconducting")
          ? "superconducting"
          : "simulated",
  contact_email: `${provider.name.toLowerCase()}@${provider.region.replace(/\s+/g, "")}.lidmas.dev`,
  supported_formats: ["jsonl", "parquet", "csv"],
  supports_scientific: true,
  supports_benchmark: true,
  supports_replay: true,
  supports_live: provider.type.includes("Superconducting"),
  last_seen: "2026-04-20T14:20:00Z",
  readiness_note: "Fixture provider in mock mode",
  notes: `Optimized for ${GKP_SCENARIO_NAME}`,
  created_at: ISO_BASE,
  updated_at: "2026-04-20T14:20:00Z",
}));

export const gkpJobRuntime: GkpJobRuntime[] = [
  {
    id: "#JOB-001",
    name: "Syndrome Extraction",
    status: "Running",
    progress: 65,
    provider: "Provider-01",
    duration: "2.1s",
    runs: "24/50",
    successRate: "98.5%",
    created: "2m ago",
  },
  {
    id: "#JOB-002",
    name: "Error Correction Round 1",
    status: "Completed",
    progress: 100,
    provider: "Provider-02",
    duration: "1.8s",
    runs: "50/50",
    successRate: "99.2%",
    created: "5m ago",
  },
  {
    id: "#JOB-003",
    name: "Logical State Preparation",
    status: "Pending",
    progress: 0,
    provider: "Provider-03",
    duration: "—",
    runs: "0/30",
    successRate: "—",
    created: "1m ago",
  },
  {
    id: "#JOB-004",
    name: "Surface Code Decoder",
    status: "Completed",
    progress: 100,
    provider: "Provider-04",
    duration: "3.2s",
    runs: "100/100",
    successRate: "97.8%",
    created: "10m ago",
  },
  {
    id: "#JOB-005",
    name: "Tanner Code Processing",
    status: "Running",
    progress: 42,
    provider: "Provider-01",
    duration: "1.9s",
    runs: "21/50",
    successRate: "96.5%",
    created: "3m ago",
  },
  {
    id: "#JOB-006",
    name: "Stabilizer Measurement",
    status: "Failed",
    progress: 100,
    provider: "Provider-03",
    duration: "0.8s",
    runs: "8/40",
    successRate: "85.0%",
    created: "7m ago",
  },
];

function mapRuntimeStatusToApi(status: GkpJobRuntime["status"]): JobStatus {
  if (status === "Completed") {
    return "completed";
  }
  if (status === "Running") {
    return "running";
  }
  if (status === "Failed") {
    return "failed";
  }
  return "queued";
}

export const gkpJobs: Job[] = gkpJobRuntime.map((job, index) => {
  const provider = gkpProviderRuntime.find((providerRuntime) => providerRuntime.name === job.provider);
  const createdAt = `2026-04-20T14:${(6 + index).toString().padStart(2, "0")}:00Z`;
  return {
    id: `a338f7a2-31fd-4fcd-b17a-7adf2f9a${(100 + index).toString().slice(-3)}`,
    provider_id: provider?.id ?? gkpProviderRuntime[0].id,
    dataset_label: job.name,
    decoders: ["bp_osd", "mwpm_gkp", "union_find"],
    priority: 5,
    status: mapRuntimeStatusToApi(job.status),
    message: `Scenario ${GKP_SCENARIO_NAME}`,
    created_at: createdAt,
    updated_at: createdAt,
    started_at: job.status === "Pending" ? null : createdAt,
    completed_at: job.status === "Completed" || job.status === "Failed" ? "2026-04-20T14:30:00Z" : null,
  };
});

const rounds = 24;
const stabilizers = 12;
const noiseLength = 30;

const gkpNoiseSamples: NoiseSample[] = Array.from({ length: noiseLength }, (_, index) => ({
  index,
  physical_error_rate: 0.006 + (Math.sin(index / 4) + 1) * 0.0045,
  displacement_sigma: 0.12 + (Math.cos(index / 5) + 1) * 0.09,
  photon_loss_rate: 0.009 + (Math.sin(index / 6) + 1) * 0.003,
}));

const gkpSyndromeSamples: SyndromeSample[] = Array.from({ length: rounds * stabilizers }, (_, index) => {
  const round = Math.floor(index / stabilizers);
  const stabilizerIndex = index % stabilizers;
  const wave = Math.sin((round + 1) * (stabilizerIndex + 2) * 0.21);
  const triggered = Math.abs(wave) > 0.62;
  return {
    round,
    stabilizer: `S${(stabilizerIndex + 1).toString().padStart(2, "0")}`,
    value: triggered ? (wave >= 0 ? 1 : -1) : 0,
    is_triggered: triggered,
  };
});

const oscillatorModes = 8;
const gkpOscillatorStates: GkpOscillatorStateSample[] = Array.from(
  { length: rounds * oscillatorModes },
  (_, index) => {
    const round = Math.floor(index / oscillatorModes);
    const modeIndex = index % oscillatorModes;
    const noise = gkpNoiseSamples[Math.min(gkpNoiseSamples.length - 1, round)];
    const theta = (modeIndex / oscillatorModes) * Math.PI * 2 + round * 0.17;
    const radiusBase = 0.55 + Math.sin(round * 0.23 + modeIndex * 0.41) * 0.22;
    const radius = radiusBase + (noise.displacement_sigma - 0.12) * 1.45;
    const q = Number((radius * Math.cos(theta)).toFixed(4));
    const p = Number((radius * Math.sin(theta)).toFixed(4));
    const variance = Number((0.04 + Math.abs(Math.sin(theta + round * 0.11)) * 0.08).toFixed(4));
    const energy = Number((0.18 + Math.abs(Math.cos(theta - round * 0.08)) * 0.24).toFixed(4));
    return {
      round,
      mode: `M${(modeIndex + 1).toString().padStart(2, "0")}`,
      q,
      p,
      variance,
      energy,
      flagged: Math.abs(q) > 0.78 || Math.abs(p) > 0.78 || variance > 0.1,
    };
  },
);

const interventionDecoders = ["bp_osd", "mwpm_gkp", "union_find"];
const gkpDecoderInterventions: DecoderIntervention[] = interventionDecoders.flatMap((decoder, decoderIndex) =>
  Array.from({ length: rounds }, (_, round) => ({
    decoder,
    round,
    flips: Math.max(1, Math.round((2.4 + decoderIndex * 0.9) * (1 + Math.sin(round * 0.31) * 0.18))),
    residual_weight: Math.max(1, Math.round((1.6 + decoderIndex * 0.55) * (1 + Math.cos(round * 0.37) * 0.2))),
  })),
);

export const gkpRunTelemetry: RunTelemetry = {
  run_id: RUN_ID,
  request_count: 2_400,
  rounds,
  stabilizer_count: stabilizers,
  warning_rate: 0.17,
  noise_samples: gkpNoiseSamples,
  syndrome_samples: gkpSyndromeSamples,
  gkp_oscillator_states: gkpOscillatorStates,
  decoder_interventions: gkpDecoderInterventions,
  updated_at: "2026-04-20T14:35:00Z",
};

export const gkpRuns: Run[] = [
  {
    id: RUN_ID,
    job_id: gkpJobs[0]?.id ?? null,
    provider_id: gkpProviders[0].id,
    dataset_label: "gkp_surface_25_rounds_24",
    decoders: interventionDecoders,
    status: "running" satisfies RunStatus,
    message: "GKP decode loop is active",
    artifacts: [
      {
        name: "syndrome_trace",
        kind: "jsonl",
        path: "/artifacts/runs/gkp/syndrome_trace.jsonl",
        sha256: null,
        created_at: "2026-04-20T14:10:00Z",
      },
      {
        name: "decoder_metrics",
        kind: "csv",
        path: "/artifacts/runs/gkp/decoder_metrics.csv",
        sha256: null,
        created_at: "2026-04-20T14:11:30Z",
      },
    ],
    metrics: {
      avg_flip_count: 3.2,
      nonempty_flip_rate: 0.34,
      syndrome_satisfaction_rate: 0.92,
      residual_nonzero_rate: 0.19,
      warning_rate: 0.17,
    },
    created_at: "2026-04-20T14:08:00Z",
    updated_at: "2026-04-20T14:35:00Z",
  },
  {
    id: "01ab96dd-76d5-4508-8b96-07814fddce10",
    job_id: gkpJobs[1]?.id ?? null,
    provider_id: gkpProviders[1].id,
    dataset_label: "gkp_surface_17_rounds_18",
    decoders: interventionDecoders,
    status: "finished" satisfies RunStatus,
    message: "Run completed",
    artifacts: [],
    metrics: {
      avg_flip_count: 2.8,
      nonempty_flip_rate: 0.3,
      syndrome_satisfaction_rate: 0.95,
      residual_nonzero_rate: 0.14,
      warning_rate: 0.11,
    },
    created_at: "2026-04-20T13:30:00Z",
    updated_at: "2026-04-20T13:58:00Z",
  },
];

export const gkpLogs: GkpLogEntry[] = [
  {
    timestamp: "2026-04-20 15:26:42.891",
    level: "INFO",
    message: "Initialized GKP lattice decoder pipeline",
    source: "core/init.rs:234",
  },
  {
    timestamp: "2026-04-20 15:26:43.120",
    level: "INFO",
    message: "Connected to photonic provider for displacement channel stream",
    source: "providers/manager.rs:156",
  },
  {
    timestamp: "2026-04-20 15:27:02.761",
    level: "SUCCESS",
    message: "Round-12 syndrome extraction converged under threshold",
    source: "decoder/gkp.rs:410",
  },
  {
    timestamp: "2026-04-20 15:27:15.789",
    level: "WARN",
    message: "Residual weight spike observed for bp_osd at round 17",
    source: "monitoring/alerts.rs:112",
  },
  {
    timestamp: "2026-04-20 15:28:02.341",
    level: "ERROR",
    message: "Provider-03 returned timeout during parity check replay",
    source: "providers/health.rs:156",
  },
  {
    timestamp: "2026-04-20 15:28:02.512",
    level: "INFO",
    message: "Failover initiated and workload moved to Provider-02",
    source: "providers/failover.rs:89",
  },
  {
    timestamp: "2026-04-20 15:29:12.678",
    level: "SUCCESS",
    message: "GKP run checkpoint saved with 98.6% stabilizer agreement",
    source: "jobs/executor.rs:710",
  },
];

export const gkpAlerts: GkpAlertItem[] = [
  {
    id: 1,
    title: "Provider-03 Timeout Burst",
    level: "critical",
    message: "Provider-03 exceeded timeout SLA for 4 consecutive telemetry windows.",
    triggered: "Triggered: 15:28 (7 min ago)",
    meta: "Affected: 2 active runs",
  },
  {
    id: 2,
    title: "Residual Weight Trend",
    level: "warning",
    message: "Residual nonzero rate climbed above 0.20 in GKP benchmark run.",
    triggered: "Triggered: 15:26 (9 min ago)",
    meta: "Current: 0.22",
  },
  {
    id: 3,
    title: "Maintenance Window Scheduled",
    level: "info",
    message: "Provider-01 firmware patch window starts at 2026-04-21 02:00 UTC.",
    triggered: "Triggered: 14:10",
    meta: "Status: Acknowledged",
  },
];

export const gkpAlertRules: GkpAlertRule[] = [
  {
    id: 1,
    name: "Provider Timeout SLA",
    condition: "Trigger when timeout ratio > 1% for 5 minutes",
    enabled: true,
  },
  {
    id: 2,
    name: "Residual Weight Drift",
    condition: "Trigger when residual_nonzero_rate > 0.20",
    enabled: true,
  },
  {
    id: 3,
    name: "Syndrome Integrity Drop",
    condition: "Trigger when syndrome_satisfaction_rate < 0.90",
    enabled: true,
  },
  {
    id: 4,
    name: "Decode Throughput Regression",
    condition: "Trigger when requests/second drops by 25%",
    enabled: false,
  },
];
