import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ChevronDown, ChevronUp, Power, ShieldCheck } from "lucide-react";
import { createPortal } from "react-dom";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError } from "../../api/client";
import {
  useCreateIntegrationSession,
  useCreateRun,
  useHealth,
  useIntegrationSessionLogs,
  useIntegrationSessions,
  useJobs,
  useProviders,
  useRunTelemetry,
  useRuns,
  useSetIbmApiKey,
  useStopIntegrationSession,
} from "../../api/hooks";
import type {
  GkpOscillatorStateSample,
  IntegrationAdapterId,
  IntegrationSession,
  IntegrationSessionConfig,
  IntegrationSessionStatus,
  Provider,
  Run,
  RunTelemetry,
  SyndromeSample,
} from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { useSessionControl, type SessionLaunchMode } from "../../data/sessionControl";
import {
  DECODERS,
  DECODER_PROFILES,
  decoderMatchesKey,
  decoderLabel,
  parseDecoderKey,
} from "../../data/decoders";
import type { DecoderKey } from "../../data/decoders";
import { gkpHealth, gkpJobs, gkpProviders, gkpRunTelemetry, gkpRuns } from "../../data/gkpFixtures";
import {
  SCIENTIFIC_CARD_CONTRACTS,
  SCIENTIFIC_FIELD_LABELS,
  SCIENTIFIC_PRIMARY_CARD_ORDER,
  SCIENTIFIC_SECONDARY_CARD_ORDER,
  type ScientificCardKey,
  type ScientificField,
} from "../scientific/contracts";
import { ScientificEmptyState } from "../scientific/ScientificEmptyState";
import { ScientificIntegrityAlert } from "../scientific/ScientificIntegrityAlert";
import { ScientificMetricCard } from "../scientific/ScientificMetricCard";
import { SessionLauncherButton } from "../scientific/SessionLauncherButton";
import { ScientificStateBanner } from "../scientific/ScientificStateBanner";
import { StartBenchmarkSessionDialog } from "../scientific/StartBenchmarkSessionDialog";
import {
  StartCircuitDesignDialog,
  type CircuitDesignDraft,
  type CircuitProviderFamily,
} from "../scientific/StartCircuitDesignDialog";
import { StartIbmApiKeyDialog } from "../scientific/StartIbmApiKeyDialog";
import { StartReplaySessionDialog } from "../scientific/StartReplaySessionDialog";
import {
  decoderRowMatchesActive,
  resolveScientificState,
  scientificStateLabel,
  scientificStateStatusClass,
} from "../scientific/stateMachine";

type DashboardChart = "noise" | "success" | "error" | "latency";
type TimeRangeFilter = "1h" | "6h" | "24h" | "7d";
type DashboardRole = "viewer" | "operator" | "admin";
type EncodingMapMode = "surface" | "gkp";
type OuterCodeDistance = 3 | 5 | 7;

interface MonitoringPoint {
  slot: string;
  noise: number;
  success: number;
  error: number;
  latency: number;
}

interface MonitoringPointWithCompare extends MonitoringPoint {
  compareNoise?: number | null;
  compareSuccess?: number | null;
  compareError?: number | null;
  compareLatency?: number | null;
}

interface MonitoringSeriesResult {
  series: MonitoringPoint[];
  hasDecoderSignal: boolean;
}

interface PhysicalNoisePoint {
  round: number;
  physicalErrorPct: number;
  photonLossPct: number;
  displacementSigma: number;
}

interface OperationalKpiCardModel {
  key: string;
  label: string;
  value: string;
  trendText: string;
  trendDelta: number;
  trendUpGood: boolean;
}

interface WorkflowAlertItem {
  id: string;
  level: "critical" | "warning" | "info";
  title: string;
  detail: string;
  metric: string;
}

interface AlertWorkflowState {
  acknowledged: boolean;
  owner: string;
  notes: string;
}

interface DrilldownState {
  source: "physical" | "realtime";
  title: string;
  summary: string;
  keyValues: Array<{ label: string; value: string }>;
  timeline: string[];
}

interface ChartEventPayload<T> {
  activePayload?: Array<{ payload?: T }>;
}

interface PhysicalLegendSignal {
  id: string;
  label: string;
  color?: string;
  format: (point: PhysicalNoisePoint | null) => string;
}

interface QecLatticeNode {
  key: string;
  label: string;
  x: number;
  y: number;
  triggered: boolean;
  value: number;
}

interface QecLatticeEdge {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface QecLatticeModel {
  nodes: QecLatticeNode[];
  edges: QecLatticeEdge[];
  columns: number;
  rows: number;
}

interface GkpOscillatorMapPoint {
  key: string;
  mode: string;
  round: number;
  q: number;
  p: number;
  variance: number;
  energy: number;
  flagged: boolean;
  x: number;
  y: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function numericValue(value: unknown): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (Array.isArray(value) && value.length > 0) {
    return numericValue(value[0]);
  }
  return 0;
}

function chartLabel(chart: DashboardChart): string {
  if (chart === "noise") {
    return "Noise Level";
  }
  if (chart === "success") {
    return "Success Rate";
  }
  if (chart === "error") {
    return "Error Rate";
  }
  return "Latency Trend";
}

const PHYSICAL_LEGEND_SIGNALS: PhysicalLegendSignal[] = [
  {
    id: "sigma",
    label: "Displacement Sigma",
    color: "#3f89ea",
    format: (point) => (point ? point.displacementSigma.toFixed(4) : "N/A"),
  },
  {
    id: "photon-loss",
    label: "Photon Loss Rate",
    color: "#f0982f",
    format: (point) => (point ? `${point.photonLossPct.toFixed(3)}%` : "N/A"),
  },
  {
    id: "physical-error",
    label: "Physical Error Rate",
    color: "#e25564",
    format: (point) => (point ? `${point.physicalErrorPct.toFixed(3)}%` : "N/A"),
  },
];

function providerKindLabel(kind: string): string {
  if (kind === "superconducting") {
    return "Superconducting Qubits";
  }
  if (kind === "photonic") {
    return "Photonic";
  }
  if (kind === "trapped_ion") {
    return "Trapped Ion";
  }
  if (kind === "simulated") {
    return "Simulated";
  }
  return "Other";
}

interface QuickLaunchPlan {
  adapterId: IntegrationAdapterId;
  config: IntegrationSessionConfig;
}

interface LaunchSessionInput {
  mode: SessionLaunchMode;
  provider: Provider;
  decoders: DecoderKey[];
  datasetHint: string;
  circuitDesign?: CircuitDesignDraft;
  runSource?: Run | null;
  ibmLiveSourceMode?: "metadata" | "qpu";
  ibmInstance?: string;
}

interface ReplaySourceOption {
  runId: string;
  datasetLabel: string;
  providerName: string;
  updatedAtLabel: string;
}

type ProviderFamily = "xanadu" | "ankaa" | "ibm" | "pennylane" | "qiskit" | "cirq" | "unknown";

function sessionModeFromAdapter(adapterId: IntegrationAdapterId): SessionLaunchMode {
  if (adapterId === "ibm_superconducting_live") {
    return "scientific";
  }
  return "replay";
}

function resolveProviderFamily(provider: Provider): ProviderFamily {
  const identitySignal = [provider.name, provider.contact_email ?? ""]
    .join(" ")
    .trim()
    .toLowerCase();
  // Resolve software stacks from provider identity only; shared notes may mention multiple stacks.
  if (identitySignal.includes("qiskit")) {
    return "qiskit";
  }
  if (identitySignal.includes("cirq")) {
    return "cirq";
  }
  if (identitySignal.includes("pennylane")) {
    return "pennylane";
  }
  if (identitySignal.includes("xanadu")) {
    return "xanadu";
  }
  if (identitySignal.includes("ankaa")) {
    return "ankaa";
  }
  if (identitySignal.includes("ibm")) {
    return "ibm";
  }

  const metadataSignal = [provider.readiness_note ?? "", provider.notes ?? ""]
    .join(" ")
    .trim()
    .toLowerCase();
  if (metadataSignal.includes("xanadu")) {
    return "xanadu";
  }
  if (metadataSignal.includes("ankaa")) {
    return "ankaa";
  }
  if (metadataSignal.includes("ibm")) {
    return "ibm";
  }
  if (provider.kind === "photonic") {
    return "xanadu";
  }
  if (provider.kind === "superconducting") {
    if (provider.supports_live) {
      return "ibm";
    }
    if (provider.supports_replay) {
      return "ankaa";
    }
    return "unknown";
  }
  return "unknown";
}

function familyRequiresNeuralModel(family: ProviderFamily): boolean {
  return (
    family === "xanadu" ||
    family === "pennylane" ||
    family === "qiskit" ||
    family === "cirq"
  );
}

function workflowForProviderFamily(family: ProviderFamily): string | undefined {
  if (family === "pennylane" || family === "qiskit" || family === "cirq") {
    return "paper_04";
  }
  return undefined;
}

function adapterRequiresNeuralModel(adapterId: IntegrationAdapterId): boolean {
  return (
    adapterId === "xanadu_gkp_remote_replay" ||
    adapterId === "pennylane_surface_replay" ||
    adapterId === "qiskit_surface_replay" ||
    adapterId === "cirq_surface_replay"
  );
}

function supportsSoftwareCircuitDesign(provider: Provider): boolean {
  const family = resolveProviderFamily(provider);
  return family === "pennylane" || family === "qiskit" || family === "cirq";
}

function providerReady(provider: Provider | null): boolean {
  return provider != null && provider.status !== "offline";
}

function runHasScientificEvidence(run: Run): boolean {
  if (run.status === "created") {
    return false;
  }
  const metrics = run.metrics;
  if (!metrics) {
    return false;
  }
  return (
    metrics.scientific_validation_ready === true ||
    metrics.logical_error_rate != null ||
    metrics.logical_failures != null ||
    metrics.logical_trials != null ||
    metrics.physical_error_rate != null ||
    metrics.physical_error_events != null ||
    metrics.physical_error_opportunities != null ||
    metrics.request_line_count != null ||
    metrics.response_line_count != null ||
    metrics.rounds != null ||
    metrics.stabilizer_count != null ||
    metrics.syndrome_opportunities != null ||
    metrics.residual_syndrome_events != null ||
    metrics.expanded_shot_count != null ||
    metrics.syndrome_satisfaction_rate != null ||
    (metrics.decoder_exact_metrics?.length ?? 0) > 0 ||
    (metrics.decoder_rankings?.length ?? 0) > 0
  );
}

function scientificTransport(provider: Provider): "live" | "replay" | null {
  if (!provider.supports_scientific) {
    return null;
  }
  const family = resolveProviderFamily(provider);
  if (family === "ibm") {
    if (provider.supports_live) {
      return "live";
    }
    if (provider.supports_replay) {
      return "replay";
    }
    return null;
  }
  if (provider.supports_replay) {
    return "replay";
  }
  if (provider.supports_live) {
    return "live";
  }
  return null;
}

function buildQuickLaunchPlan(
  provider: Provider,
  _selectedDecoder: DecoderKey,
  neuralModelPath: string,
  mode: SessionLaunchMode,
): QuickLaunchPlan | null {
  const family = resolveProviderFamily(provider);
  const scientificMode = scientificTransport(provider);
  if (mode === "replay" && !provider.supports_replay) {
    return null;
  }
  if ((mode === "scientific" || mode === "benchmark") && scientificMode == null) {
    return null;
  }

  if (family === "xanadu") {
    if (!provider.supports_replay) {
      return null;
    }
    const trimmedModelPath = neuralModelPath.trim();
    return {
      adapterId: "xanadu_gkp_remote_replay",
      config: {
        remote: "macstudio",
        remote_input_root: "examples/results/hardware_integration/downloads/gkp/full",
        neural_model_path: trimmedModelPath || undefined,
      },
    };
  }

  if (family === "ibm") {
    if (mode === "replay") {
      return null;
    }
    if (!provider.supports_live) {
      return null;
    }
    return {
      adapterId: "ibm_superconducting_live",
      config: {
        backend_name: "ibm_kingston",
        poll_interval: 30,
      },
    };
  }

  if (family === "ankaa") {
    if (mode !== "scientific" && mode !== "benchmark" && !provider.supports_replay) {
      return null;
    }
    if ((mode === "scientific" || mode === "benchmark") && scientificMode !== "replay") {
      return null;
    }
    return {
      adapterId: "ankaa_superconducting_replay",
      config: {
        input_path: "hardware_integration/ankaa/superconducting/ankaa_fixture_example.json",
      },
    };
  }

  if (family === "pennylane" || family === "qiskit" || family === "cirq") {
    if (mode !== "scientific" && mode !== "benchmark" && !provider.supports_replay) {
      return null;
    }
    if ((mode === "scientific" || mode === "benchmark") && scientificMode !== "replay") {
      return null;
    }
    const trimmedModelPath = neuralModelPath.trim();
    const adapterId: IntegrationAdapterId =
      family === "pennylane"
        ? "pennylane_surface_replay"
        : family === "qiskit"
          ? "qiskit_surface_replay"
          : "cirq_surface_replay";
    return {
      adapterId,
      config: {
        simulator_code_family: "surface",
        simulator_shots: 240,
        simulator_distance: 5,
        simulator_rounds: 4,
        simulator_error_rate: 0.08,
        simulator_sigma: 0.18,
        neural_model_path: trimmedModelPath || undefined,
      },
    };
  }

  return null;
}

function parseTimeRange(value: string | null): TimeRangeFilter {
  if (value === "6h" || value === "24h" || value === "7d") {
    return value;
  }
  return "1h";
}

function parseRole(value: string | null): DashboardRole {
  if (value === "viewer" || value === "operator") {
    return value;
  }
  return "admin";
}

function parseOuterCodeDistance(value: string | null): OuterCodeDistance {
  if (value === "5") {
    return 5;
  }
  if (value === "7") {
    return 7;
  }
  return 3;
}

function parseBooleanFlag(value: string | null): boolean {
  return value === "1" || value === "true" || value === "yes";
}

function percentDelta(current: number, previous: number): number {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) {
    return 0;
  }
  const baseline = Math.max(1e-9, Math.abs(previous));
  return ((current - previous) / baseline) * 100;
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((p / 100) * sorted.length)));
  return sorted[index];
}

function formatTrend(deltaPct: number): string {
  const absValue = Math.abs(deltaPct);
  const direction = deltaPct >= 0 ? "▲" : "▼";
  return `${direction} ${absValue.toFixed(1)}%`;
}

function asCount(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return Math.trunc(value);
}

function formatCount(value: number | null | undefined): string {
  const count = asCount(value);
  return count == null ? "—" : count.toLocaleString();
}

function formatCompactCount(value: number | null | undefined): string {
  const count = asCount(value);
  if (count == null) {
    return "—";
  }
  const units: Array<{ threshold: number; suffix: string }> = [
    { threshold: 1_000_000_000_000, suffix: "T" },
    { threshold: 1_000_000_000, suffix: "B" },
    { threshold: 1_000_000, suffix: "M" },
    { threshold: 1_000, suffix: "K" },
  ];
  for (const unit of units) {
    if (count >= unit.threshold) {
      const scaled = count / unit.threshold;
      const digits = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
      return `${scaled.toFixed(digits)}${unit.suffix}`;
    }
  }
  return count.toLocaleString();
}

function formatPercentWithCounts(
  numerator: number | null | undefined,
  denominator: number | null | undefined,
  digits = 2,
): string {
  const n = asCount(numerator);
  const d = asCount(denominator);
  if (n == null || d == null || d <= 0 || n > d) {
    return "—";
  }
  const pct = (n / d) * 100;
  return `${n.toLocaleString()} / ${d.toLocaleString()} = ${pct.toFixed(digits)}%`;
}

function formatRatioWithCounts(
  numerator: number | null | undefined,
  denominator: number | null | undefined,
  digits = 3,
): string {
  const n = asCount(numerator);
  const d = asCount(denominator);
  if (n == null || d == null || d <= 0) {
    return "—";
  }
  return `${n.toLocaleString()} / ${d.toLocaleString()} = ${(n / d).toFixed(digits)}`;
}

function formatOverheadMapping(
  rounds: number | null | undefined,
  stabilizerCount: number | null | undefined,
  providerKind: Provider["kind"] | null | undefined,
): string {
  const normalizedRounds = asCount(rounds);
  const normalizedStabilizerCount = asCount(stabilizerCount);
  if (
    normalizedRounds == null ||
    normalizedStabilizerCount == null ||
    normalizedRounds <= 0 ||
    normalizedStabilizerCount <= 0
  ) {
    return "—";
  }
  const mappedOverhead = Math.round(
    normalizedStabilizerCount * normalizedRounds * (providerKind === "photonic" ? 1.4 : 2.1),
  );
  if (providerKind === "photonic") {
    return `${mappedOverhead.toLocaleString()} CV states / logical mode`;
  }
  return `${mappedOverhead.toLocaleString()} physical qubits / logical qubit`;
}

function formatAgo(isoText: string | null | undefined): string {
  if (!isoText) {
    return "unknown";
  }
  const parsed = new Date(isoText).getTime();
  if (!Number.isFinite(parsed)) {
    return "unknown";
  }
  const deltaMs = Date.now() - parsed;
  const deltaMins = Math.max(0, Math.floor(deltaMs / 60_000));
  if (deltaMins < 1) {
    return "just now";
  }
  if (deltaMins < 60) {
    return `${deltaMins}m ago`;
  }
  const hours = Math.floor(deltaMins / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatClock(isoText: string | null | undefined): string {
  if (!isoText) {
    return "--:--:--";
  }
  const date = new Date(isoText);
  if (!Number.isFinite(date.getTime())) {
    return "--:--:--";
  }
  return date.toLocaleTimeString([], { hour12: false });
}

function sessionStatusLabel(status: IntegrationSessionStatus): string {
  if (status === "starting") {
    return "Starting";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "finished") {
    return "Finished";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Failed";
}

function sessionStatusLevel(status: IntegrationSessionStatus): "info" | "warn" | "critical" | "ok" {
  if (status === "finished") {
    return "ok";
  }
  if (status === "failed") {
    return "critical";
  }
  if (status === "cancelled") {
    return "warn";
  }
  return "info";
}

function inferLogLevel(stream: "stdout" | "stderr" | "system", line: string): "info" | "warn" | "critical" | "ok" {
  const normalized = line.trim().toLowerCase();
  if (
    stream === "stderr" ||
    normalized.includes("error") ||
    normalized.includes("failed") ||
    normalized.includes("exception") ||
    normalized.includes("traceback") ||
    normalized.includes("timed out") ||
    normalized.includes("timeout")
  ) {
    return "critical";
  }
  if (normalized.includes("warn")) {
    return "warn";
  }
  if (
    normalized.includes("started") ||
    normalized.includes("running") ||
    normalized.includes("completed") ||
    normalized.includes("finished") ||
    normalized.includes("success")
  ) {
    return "ok";
  }
  return stream === "system" ? "info" : "ok";
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  if (bytes < 1024) {
    return `${Math.round(bytes)} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function stabilizerSortKey(label: string): number {
  const match = label.match(/\d+/);
  if (!match) {
    return Number.MAX_SAFE_INTEGER;
  }
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}

function stabilizerLabel(index: number): string {
  return `S${(index + 1).toString().padStart(2, "0")}`;
}

function timeRangeConfig(range: TimeRangeFilter): { points: number; stepMinutes: number } {
  if (range === "6h") {
    return { points: 72, stepMinutes: 5 };
  }
  if (range === "24h") {
    return { points: 288, stepMinutes: 5 };
  }
  if (range === "7d") {
    return { points: 336, stepMinutes: 30 };
  }
  return { points: 12, stepMinutes: 5 };
}

function formatTimeSlot(totalPoints: number, index: number, stepMinutes: number): string {
  const minutesBack = (totalPoints - index - 1) * stepMinutes;
  if (minutesBack >= 1_440) {
    const days = Math.round((minutesBack / 1_440) * 10) / 10;
    return `T-${days}d`;
  }
  if (minutesBack >= 60) {
    const hours = Math.round((minutesBack / 60) * 10) / 10;
    return `T-${hours}h`;
  }
  return `T-${minutesBack}m`;
}

function downsampleSeries<T>(series: T[], maxPoints: number): T[] {
  if (series.length <= maxPoints) {
    return series;
  }
  const stride = Math.ceil(series.length / maxPoints);
  return series.filter((_, index) => index % stride === 0 || index === series.length - 1);
}

function extractChartPayload<T>(event: unknown): T | null {
  if (!event || typeof event !== "object") {
    return null;
  }
  const payloadContainer = event as ChartEventPayload<T>;
  const firstPayload = payloadContainer.activePayload?.[0];
  if (!firstPayload || !firstPayload.payload) {
    return null;
  }
  return firstPayload.payload;
}

function metricValue(point: MonitoringPointWithCompare, chart: DashboardChart, compare: boolean): number {
  if (chart === "noise") {
    return compare ? point.compareNoise ?? 0 : point.noise;
  }
  if (chart === "success") {
    return compare ? point.compareSuccess ?? 0 : point.success;
  }
  if (chart === "error") {
    return compare ? point.compareError ?? 0 : point.error;
  }
  return compare ? point.compareLatency ?? 0 : point.latency;
}

function buildMonitoringSeries(
  decoder: DecoderKey,
  points: number,
  stepMinutes: number,
  isMock: boolean,
  jobsCount: number,
  runsCount: number,
  providerCount: number,
): MonitoringPoint[] {
  const noiseBase = isMock ? 0.017 : 0.013;
  const successBase = isMock ? 97.8 : 96.6;
  const latencyBase = isMock ? 46 : 41;
  const decoderProfile = DECODER_PROFILES[decoder];
  const providerFactor = clamp(providerCount / 12, 0.1, 1.25);

  return Array.from({ length: points }, (_, index) => {
    const wave = Math.sin(index * 0.66) * decoderProfile.waveScale;
    const pulse = Math.cos(index * 0.37) * decoderProfile.waveScale;
    const loadFactor = jobsCount * 0.06 + runsCount * 0.1;
    const success = clamp(
      successBase + decoderProfile.successBias + pulse * 1.1 - loadFactor * 0.08 + providerFactor * 0.7,
      87,
      99.8,
    );
    const error = clamp(100 - success, 0.2, 12);
    const latency = clamp(
      latencyBase + decoderProfile.latencyBias + wave * 5.5 + loadFactor * 0.95 + providerFactor * 2.1,
      18,
      180,
    );
    const noise = clamp(
      noiseBase + decoderProfile.noiseBias + wave * 0.0019 + jobsCount * 0.00025 + providerFactor * 0.00035,
      0.004,
      0.04,
    );

    return {
      slot: formatTimeSlot(points, index, stepMinutes),
      noise: Number(noise.toFixed(4)),
      success: Number(success.toFixed(2)),
      error: Number(error.toFixed(2)),
      latency: Number(latency.toFixed(1)),
    };
  });
}

function buildMonitoringSeriesFromTelemetry(
  decoder: DecoderKey,
  telemetry: RunTelemetry | null | undefined,
  points: number,
  stepMinutes: number,
): MonitoringSeriesResult {
  const emptySeries = Array.from({ length: points }, (_, index) => ({
    slot: formatTimeSlot(points, index, stepMinutes),
    noise: 0,
    success: 0,
    error: 0,
    latency: 0,
  }));
  if (!telemetry) {
    return { series: emptySeries, hasDecoderSignal: false };
  }

  const inferredRounds = Math.max(
    telemetry.rounds ?? 0,
    telemetry.syndrome_samples.reduce((maxRound, sample) => Math.max(maxRound, sample.round + 1), 0),
    telemetry.decoder_interventions.reduce((maxRound, row) => Math.max(maxRound, row.round + 1), 0),
  );
  const rounds = Math.max(1, inferredRounds);

  const syndromeByRound = new Map<number, { triggered: number; total: number }>();
  telemetry.syndrome_samples.forEach((sample) => {
    const current = syndromeByRound.get(sample.round) ?? { triggered: 0, total: 0 };
    current.total += 1;
    if (sample.is_triggered) {
      current.triggered += 1;
    }
    syndromeByRound.set(sample.round, current);
  });

  const decoderRows = telemetry.decoder_interventions.filter((row) =>
    decoderMatchesKey(row.decoder, decoder),
  );
  const hasDecoderSignal = decoderRows.length > 0;
  const interventionsByRound = new Map<number, { flips: number; residual: number }>();
  decoderRows.forEach((row) => {
    const current = interventionsByRound.get(row.round) ?? { flips: 0, residual: 0 };
    current.flips += row.flips;
    current.residual += row.residual_weight;
    interventionsByRound.set(row.round, current);
  });

  const sortedNoise = [...telemetry.noise_samples].sort((left, right) => left.index - right.index);
  const noiseForRound = (round: number) => {
    if (sortedNoise.length === 0) {
      return telemetry.warning_rate ?? 0.012;
    }
    const safeIndex = Math.min(sortedNoise.length - 1, Math.max(0, round));
    return sortedNoise[safeIndex]?.physical_error_rate ?? telemetry.warning_rate ?? 0.012;
  };

  const series = Array.from({ length: points }, (_, index) => {
    const startRound = Math.floor((index * rounds) / points);
    const endRound = Math.max(startRound + 1, Math.floor(((index + 1) * rounds) / points));
    const boundedEnd = Math.min(rounds, endRound);

    let bucketRounds = 0;
    let totalTriggered = 0;
    let totalChecks = 0;
    let flips = 0;
    let residual = 0;
    let noiseAccum = 0;

    for (let round = startRound; round < boundedEnd; round += 1) {
      bucketRounds += 1;
      const syndromeStats = syndromeByRound.get(round);
      if (syndromeStats) {
        totalTriggered += syndromeStats.triggered;
        totalChecks += syndromeStats.total;
      }
      const intervention = interventionsByRound.get(round);
      if (intervention) {
        flips += intervention.flips;
        residual += intervention.residual;
      }
      noiseAccum += noiseForRound(round);
    }

    const roundsInBucket = Math.max(1, bucketRounds);
    const triggerRatio = totalChecks > 0 ? totalTriggered / totalChecks : 0;
    const flipsMean = flips / roundsInBucket;
    const residualMean = residual / roundsInBucket;
    const noiseBase = noiseAccum / roundsInBucket;
    const noise = clamp(noiseBase + triggerRatio * 0.01, 0.001, 0.08);

    const success = hasDecoderSignal
      ? clamp(99.4 - flipsMean * 2.6 - residualMean * 3.4 - triggerRatio * 19 - noise * 330, 82, 99.9)
      : clamp(88.0 - triggerRatio * 18 - noise * 240, 70, 95);
    const error = clamp(100 - success, 0.05, 30);
    const latency = hasDecoderSignal
      ? clamp(18 + flipsMean * 4.8 + residualMean * 6.4 + triggerRatio * 20 + noise * 620, 8, 320)
      : clamp(9 + triggerRatio * 11 + noise * 380, 4, 180);

    return {
      slot: formatTimeSlot(points, index, stepMinutes),
      noise: Number(noise.toFixed(4)),
      success: Number(success.toFixed(2)),
      error: Number(error.toFixed(2)),
      latency: Number(latency.toFixed(1)),
    };
  });

  return { series, hasDecoderSignal };
}

export function DecoderDashboard() {
  const navigate = useNavigate();
  const [activeChart, setActiveChart] = useState<DashboardChart>("noise");
  const [encodingMapMode, setEncodingMapMode] = useState<EncodingMapMode>("surface");
  const [isPhysicalPanelCollapsed, setPhysicalPanelCollapsed] = useState(false);
  const [drilldown, setDrilldown] = useState<DrilldownState | null>(null);
  const [alertWorkflow, setAlertWorkflow] = useState<Record<string, AlertWorkflowState>>({});
  const [showLiveConsole, setShowLiveConsole] = useState(true);
  const [showOperationalWorkflow, setShowOperationalWorkflow] = useState(true);
  const [opsLogCursor, setOpsLogCursor] = useState(0);
  const [quickLaunchMessage, setQuickLaunchMessage] = useState<string | null>(null);
  const [quickLaunchTone, setQuickLaunchTone] = useState<"info" | "success" | "error">("info");
  const [sessionLauncherMenuOpen, setSessionLauncherMenuOpen] = useState(false);
  const [circuitDesignDialogOpen, setCircuitDesignDialogOpen] = useState(false);
  const [pendingCircuitLaunch, setPendingCircuitLaunch] = useState<LaunchSessionInput | null>(null);
  const [benchmarkDialogOpen, setBenchmarkDialogOpen] = useState(false);
  const [replayDialogOpen, setReplayDialogOpen] = useState(false);
  const [ibmApiKeyDialogOpen, setIbmApiKeyDialogOpen] = useState(false);
  const [ibmApiKeyInput, setIbmApiKeyInput] = useState("");
  const [ibmLiveSourceMode, setIbmLiveSourceMode] = useState<"metadata" | "qpu">("metadata");
  const [ibmInstanceInput, setIbmInstanceInput] = useState("");
  const [ibmApiKeyError, setIbmApiKeyError] = useState<string | null>(null);
  const [pendingIbmLaunch, setPendingIbmLaunch] = useState<LaunchSessionInput | null>(null);
  const [benchmarkDecoders, setBenchmarkDecoders] = useState<DecoderKey[]>(() => DECODERS.map((decoder) => decoder.key));
  const [replaySourceRunId, setReplaySourceRunId] = useState<string>("");
  const [activeHomeSessionSnapshot, setActiveHomeSessionSnapshot] = useState<IntegrationSession | null>(null);
  const [healthProbeLatencyMs, setHealthProbeLatencyMs] = useState<number | null>(null);
  const healthProbeStartRef = useRef<number | null>(null);
  const homeSessionStatusRef = useRef<IntegrationSessionStatus | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    state: sessionControlState,
    beginLaunch,
    markRunning,
    markStopping,
    markStopped,
    markFailed,
    setActiveContext,
    clearError,
  } = useSessionControl();
  const sessionControlStatusRef = useRef(sessionControlState.status);
  const {
    mode,
    isApi,
    isMock,
    systemOff,
    setSystemOff,
    systemArmed,
    armSystem,
    activeDecoder,
    setActiveDecoder,
    neuralModelPath,
    setNeuralModelPath,
  } = useDataMode();
  const apiConnected = isApi && !systemOff;
  const apiEnabled = apiConnected && systemArmed;
  const activeHomeRunId = sessionControlState.activeRunId;
  const activeHomeSessionId = sessionControlState.activeSessionId;

  const timeRangeFilter = parseTimeRange(searchParams.get("range"));
  const providerFilter = searchParams.get("provider") ?? "all";
  const compareMode = parseBooleanFlag(searchParams.get("compare"));
  const role = parseRole(searchParams.get("role"));
  const outerCodeDistance = parseOuterCodeDistance(searchParams.get("outerDistance"));
  const compareDecoderParam = parseDecoderKey(searchParams.get("compareDecoder"));
  const fallbackCompareDecoder =
    DECODERS.find((decoder) => decoder.key !== activeDecoder)?.key ?? activeDecoder;
  const compareDecoder =
    compareDecoderParam && compareDecoderParam !== activeDecoder
      ? compareDecoderParam
      : fallbackCompareDecoder;
  const canEditWorkflow = role !== "viewer";

  const setFilterParam = (key: string, value: string, defaultValue: string) => {
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      if (!value || value === defaultValue) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, value);
      }
      return nextParams;
    });
  };

  const healthQuery = useHealth({ enabled: apiEnabled });
  const providersQuery = useProviders({ enabled: apiConnected, refetchInterval: 15_000 });
  const jobsQuery = useJobs({ enabled: apiEnabled, refetchInterval: 2_500 });
  const runsQuery = useRuns({ enabled: apiEnabled, refetchInterval: 2_500 });
  const sessionsQuery = useIntegrationSessions({ enabled: apiEnabled, refetchInterval: 2_000 });
  const createRunMutation = useCreateRun();
  const createSessionMutation = useCreateIntegrationSession();
  const setIbmApiKeyMutation = useSetIbmApiKey();
  const stopSessionMutation = useStopIntegrationSession();

  const healthDataRaw = isMock ? gkpHealth : healthQuery.data;
  const healthData = systemOff ? null : healthDataRaw;
  const providerCatalogData = isMock ? gkpProviders : providersQuery.data ?? [];
  const providersData = systemArmed ? providerCatalogData : [];
  const jobsData = systemArmed ? (isMock ? gkpJobs : jobsQuery.data ?? []) : [];
  const runsData = systemArmed ? (isMock ? gkpRuns : runsQuery.data ?? []) : [];
  const groupedProviderOptions = useMemo(() => {
    const hardware: Provider[] = [];
    const simulators: Provider[] = [];
    providerCatalogData.forEach((provider) => {
      if (provider.kind === "simulated") {
        simulators.push(provider);
        return;
      }
      hardware.push(provider);
    });
    return { hardware, simulators };
  }, [providerCatalogData]);
  const integrationSessions = systemArmed ? (isMock ? [] : sessionsQuery.data ?? []) : [];
  const sortedIntegrationSessions = useMemo(() => {
    return [...integrationSessions].sort(
      (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
    );
  }, [integrationSessions]);

  const selectableProviders = useMemo(() => {
    return providerCatalogData.filter((provider) => {
      if (providerFilter !== "all" && provider.id !== providerFilter) {
        return false;
      }
      return true;
    });
  }, [providerCatalogData, providerFilter]);

  const filteredProviders = useMemo(
    () => (systemArmed ? selectableProviders : []),
    [selectableProviders, systemArmed],
  );

  const scopedProviders = useMemo(() => (systemOff ? [] : filteredProviders), [filteredProviders, systemOff]);

  const [launcherProviderId, setLauncherProviderId] = useState<string>("auto");
  const quickLaunchProvider = useMemo(() => {
    if (providerFilter !== "all") {
      return selectableProviders[0] ?? null;
    }
    const preferred = selectableProviders.find((provider) => !provider.name.toLowerCase().includes("ibm"));
    return preferred ?? selectableProviders[0] ?? null;
  }, [providerFilter, selectableProviders]);
  const launcherProviderOptions = useMemo(() => {
    if (selectableProviders.length === 0) {
      return [];
    }
    return selectableProviders.map((provider) => ({
      id: provider.id,
      name: provider.name,
      status: provider.status,
      kind: provider.kind,
    }));
  }, [selectableProviders]);
  useEffect(() => {
    if (launcherProviderOptions.length === 0) {
      if (launcherProviderId !== "auto") {
        setLauncherProviderId("auto");
      }
      return;
    }
    if (
      launcherProviderId === "auto" ||
      !launcherProviderOptions.some((provider) => provider.id === launcherProviderId)
    ) {
      setLauncherProviderId(launcherProviderOptions[0].id);
    }
  }, [launcherProviderId, launcherProviderOptions]);
  const launchProvider = useMemo(() => {
    if (launcherProviderId === "auto") {
      return quickLaunchProvider;
    }
    return selectableProviders.find((provider) => provider.id === launcherProviderId) ?? quickLaunchProvider;
  }, [launcherProviderId, quickLaunchProvider, selectableProviders]);

  const scopedProviderIds = useMemo(
    () => new Set(scopedProviders.map((provider) => provider.id)),
    [scopedProviders],
  );

  const scopedJobs = useMemo(() => {
    return jobsData.filter((job) => scopedProviderIds.has(job.provider_id));
  }, [jobsData, scopedProviderIds]);

  const scopedRuns = useMemo(() => {
    const filtered = runsData.filter((run) => {
      if (!scopedProviderIds.has(run.provider_id)) {
        return false;
      }
      return true;
    });
    return [...filtered].sort((a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
  }, [runsData, scopedProviderIds]);

  const providerById = useMemo(
    () => new Map(providerCatalogData.map((provider) => [provider.id, provider])),
    [providerCatalogData],
  );

  const runById = useMemo(() => new Map(runsData.map((run) => [run.id, run])), [runsData]);
  const scopedIntegrationSessions = useMemo(() => {
    return sortedIntegrationSessions.filter((session) => {
      const run = runById.get(session.run_id);
      if (!run) {
        return providerFilter === "all";
      }
      return scopedProviderIds.has(run.provider_id);
    });
  }, [providerFilter, runById, scopedProviderIds, sortedIntegrationSessions]);
  const activeIntegrationSession = useMemo(() => {
    if (!isApi) {
      return null;
    }
    if (activeHomeSessionId) {
      const exactSession =
        scopedIntegrationSessions.find((session) => session.id === activeHomeSessionId) ??
        sortedIntegrationSessions.find((session) => session.id === activeHomeSessionId);
      if (exactSession) {
        return exactSession;
      }
      if (activeHomeSessionSnapshot?.id === activeHomeSessionId) {
        return activeHomeSessionSnapshot;
      }
    }
    if (activeHomeRunId) {
      const byRun =
        scopedIntegrationSessions.find((session) => session.run_id === activeHomeRunId) ??
        sortedIntegrationSessions.find((session) => session.run_id === activeHomeRunId);
      if (byRun) {
        return byRun;
      }
    }
    return (
      scopedIntegrationSessions.find(
        (session) => session.status === "running" || session.status === "starting",
      ) ??
      sortedIntegrationSessions.find(
        (session) => session.status === "running" || session.status === "starting",
      ) ??
      null
    );
  }, [
    activeHomeRunId,
    activeHomeSessionId,
    activeHomeSessionSnapshot,
    isApi,
    scopedIntegrationSessions,
    sortedIntegrationSessions,
  ]);
  const activeSessionStreaming =
    activeIntegrationSession?.status === "running" || activeIntegrationSession?.status === "starting";

  useEffect(() => {
    if (!activeHomeSessionId) {
      homeSessionStatusRef.current = null;
      return;
    }
    const homeSession =
      sortedIntegrationSessions.find((session) => session.id === activeHomeSessionId) ??
      (activeHomeSessionSnapshot?.id === activeHomeSessionId ? activeHomeSessionSnapshot : null);
    if (!homeSession) {
      return;
    }
    if (homeSessionStatusRef.current === homeSession.status) {
      return;
    }
    homeSessionStatusRef.current = homeSession.status;

    const shortId = homeSession.id.slice(0, 8).toUpperCase();
    if (homeSession.status === "finished") {
      markStopped({ preserveRun: true });
      setQuickLaunchTone("success");
      setQuickLaunchMessage(`Session #${shortId} finished.`);
      void runsQuery.refetch();
      void sessionsQuery.refetch();
    } else if (homeSession.status === "failed") {
      markFailed(homeSession.last_error ?? `Session #${shortId} failed.`);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(
        homeSession.last_error
          ? `Session #${shortId} failed: ${homeSession.last_error}`
          : `Session #${shortId} failed.`,
      );
      void runsQuery.refetch();
      void sessionsQuery.refetch();
    } else if (homeSession.status === "cancelled") {
      markStopped({ preserveRun: true });
      setQuickLaunchTone("info");
      setQuickLaunchMessage(`Session #${shortId} cancelled.`);
      void runsQuery.refetch();
      void sessionsQuery.refetch();
    }
  }, [
    activeHomeSessionId,
    activeHomeSessionSnapshot,
    markFailed,
    markStopped,
    runsQuery,
    sessionsQuery,
    sortedIntegrationSessions,
  ]);

  useEffect(() => {
    if (!activeIntegrationSession) {
      return;
    }
    if (activeIntegrationSession.status !== "running" && activeIntegrationSession.status !== "starting") {
      return;
    }
    const resolvedMode = sessionControlState.mode ?? sessionModeFromAdapter(activeIntegrationSession.adapter_id);
    if (
      sessionControlState.activeSessionId === activeIntegrationSession.id &&
      sessionControlState.activeRunId === activeIntegrationSession.run_id &&
      sessionControlState.status === "running"
    ) {
      return;
    }
    setActiveContext({
      runId: activeIntegrationSession.run_id,
      sessionId: activeIntegrationSession.id,
      mode: resolvedMode,
    });
  }, [
    activeIntegrationSession,
    sessionControlState.activeRunId,
    sessionControlState.activeSessionId,
    sessionControlState.mode,
    sessionControlState.status,
    setActiveContext,
  ]);

  const latestScopedRun = scopedRuns.length > 0 ? scopedRuns[scopedRuns.length - 1] : null;
  const latestScopedRunWithEvidence = useMemo(() => {
    for (let index = scopedRuns.length - 1; index >= 0; index -= 1) {
      const candidate = scopedRuns[index];
      if (runHasScientificEvidence(candidate)) {
        return candidate;
      }
    }
    return null;
  }, [scopedRuns]);
  const passiveRun = latestScopedRunWithEvidence ?? latestScopedRun;
  const activeRunId = activeHomeRunId ?? activeIntegrationSession?.run_id ?? passiveRun?.id ?? null;
  const activeRun = activeRunId ? runById.get(activeRunId) ?? null : passiveRun;
  const activeRunStreaming = activeRun?.status === "running" || activeRun?.status === "created";
  const streamWarmupActive = activeSessionStreaming || activeRunStreaming;
  const showingHistoricalEvidenceRun =
    !activeHomeRunId &&
    !activeIntegrationSession &&
    latestScopedRun != null &&
    latestScopedRunWithEvidence != null &&
    latestScopedRun.id !== latestScopedRunWithEvidence.id;
  const runTelemetryScientificQuery = useRunTelemetry(activeRunId, {
    enabled: apiEnabled && Boolean(activeRunId),
    scientificMode: true,
    refetchInterval: streamWarmupActive ? 1_000 : 3_000,
  });
  const runTelemetryWarmupQuery = useRunTelemetry(activeRunId, {
    enabled: apiEnabled && Boolean(activeRunId) && streamWarmupActive,
    refetchInterval: streamWarmupActive ? 1_000 : 3_000,
  });
  const sessionLogsQuery = useIntegrationSessionLogs(activeIntegrationSession?.id ?? null, 220, {
    enabled: apiEnabled && Boolean(activeIntegrationSession?.id),
    refetchInterval: activeSessionStreaming ? 1_000 : 4_000,
  });
  const runTelemetryScientific =
    isMock && activeRunId === gkpRunTelemetry.run_id
      ? gkpRunTelemetry
      : isMock || systemOff
        ? null
        : runTelemetryScientificQuery.data ?? null;
  const runTelemetryWarmup = isMock || systemOff ? null : runTelemetryWarmupQuery.data ?? null;
  const usingWarmupTelemetry =
    !isMock && streamWarmupActive && runTelemetryScientific == null && runTelemetryWarmup != null;
  const runTelemetry =
    isMock && activeRunId === gkpRunTelemetry.run_id
      ? gkpRunTelemetry
      : isMock || systemOff
        ? null
        : runTelemetryScientific ?? (usingWarmupTelemetry ? runTelemetryWarmup : null);
  const runTelemetryNotFound =
    !isMock &&
    runTelemetryScientificQuery.error instanceof ApiError &&
    runTelemetryScientificQuery.error.status === 404 &&
    !usingWarmupTelemetry;
  const runTelemetryHardError =
    !systemOff &&
    isApi &&
    Boolean(activeRunId) &&
    (runTelemetryScientificQuery.isError &&
      !(runTelemetryScientificQuery.error instanceof ApiError && runTelemetryScientificQuery.error.status === 404));
  const telemetryInitializing =
    !systemOff && isApi && Boolean(activeRunId) && streamWarmupActive && !runTelemetry && !runTelemetryHardError;
  const telemetryUnavailableForRun =
    !systemOff &&
    isApi &&
    Boolean(activeRunId) &&
    runTelemetryNotFound &&
    !telemetryInitializing;
  const syndromeSamples = runTelemetry?.syndrome_samples ?? [];

  useEffect(() => {
    const previous = sessionControlStatusRef.current;
    const current = sessionControlState.status;
    if (
      isApi &&
      activeRunId &&
      (previous === "running" || previous === "stopping") &&
      current === "idle"
    ) {
      void runsQuery.refetch();
      void sessionsQuery.refetch();
      void runTelemetryScientificQuery.refetch();
      if (streamWarmupActive) {
        void runTelemetryWarmupQuery.refetch();
      }
    }
    sessionControlStatusRef.current = current;
  }, [
    activeRunId,
    isApi,
    runTelemetryScientificQuery,
    runTelemetryWarmupQuery,
    runsQuery,
    sessionControlState.status,
    sessionsQuery,
    streamWarmupActive,
  ]);

  const healthy = healthData?.status.toLowerCase() === "ok";
  const providerCount = scopedProviders.length;
  const jobsCount = scopedJobs.length;
  const runsCount = scopedRuns.length;
  const baseProviderCount = providersData.length;
  const baseJobsCount = jobsData.length;
  const baseRunsCount = runsData.length;
  const uptimeSeconds = healthData ? Math.max(0, Math.floor(healthData.uptime_seconds)) : 0;

  const anyApiLoading =
    !systemOff &&
    isApi &&
    (healthQuery.isLoading ||
      providersQuery.isLoading ||
      jobsQuery.isLoading ||
      runsQuery.isLoading ||
      sessionsQuery.isLoading);
  const anyApiError =
    !systemOff &&
    isApi &&
    (healthQuery.isError ||
      providersQuery.isError ||
      jobsQuery.isError ||
      runsQuery.isError ||
      sessionsQuery.isError);
  const noApiEntities =
    isApi &&
    !anyApiLoading &&
    !anyApiError &&
    baseProviderCount === 0 &&
    baseJobsCount === 0 &&
    baseRunsCount === 0;

  useEffect(() => {
    if (!isApi) {
      healthProbeStartRef.current = null;
      setHealthProbeLatencyMs(45);
      return;
    }

    if (healthQuery.fetchStatus === "fetching") {
      if (healthProbeStartRef.current === null) {
        healthProbeStartRef.current =
          typeof performance !== "undefined" && typeof performance.now === "function"
            ? performance.now()
            : Date.now();
      }
      return;
    }

    if (healthProbeStartRef.current !== null) {
      const now =
        typeof performance !== "undefined" && typeof performance.now === "function"
          ? performance.now()
          : Date.now();
      const elapsed = now - healthProbeStartRef.current;
      healthProbeStartRef.current = null;
      if (Number.isFinite(elapsed) && elapsed >= 0) {
        setHealthProbeLatencyMs(Math.round(elapsed));
      }
    }
  }, [healthQuery.fetchStatus, isApi]);

  useEffect(() => {
    if (!sessionLauncherMenuOpen) {
      return;
    }
    const onWindowClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest(".session-launcher-split")) {
        return;
      }
      setSessionLauncherMenuOpen(false);
    };
    window.addEventListener("click", onWindowClick);
    return () => window.removeEventListener("click", onWindowClick);
  }, [sessionLauncherMenuOpen]);

  const activeRunsCount = useMemo(
    () => scopedRuns.filter((run) => run.status === "created" || run.status === "running").length,
    [scopedRuns],
  );
  const queuedJobsCount = useMemo(
    () => scopedJobs.filter((job) => job.status === "queued").length,
    [scopedJobs],
  );
  const latestProviderUpdate = useMemo(() => {
    if (scopedProviders.length === 0) {
      return null;
    }
    return scopedProviders
      .map((provider) => provider.updated_at)
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];
  }, [scopedProviders]);
  const latestJobUpdate = useMemo(() => {
    if (scopedJobs.length === 0) {
      return null;
    }
    return scopedJobs
      .map((job) => job.updated_at)
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];
  }, [scopedJobs]);
  const scopePayloadBytes = useMemo(() => {
    const snapshot = {
      providers: scopedProviders,
      jobs: scopedJobs,
      runs: scopedRuns,
      telemetry: runTelemetry,
    };
    const serialized = JSON.stringify(snapshot);
    if (typeof Blob !== "undefined") {
      return new Blob([serialized]).size;
    }
    return serialized.length;
  }, [runTelemetry, scopedJobs, scopedProviders, scopedRuns]);

  const hardwareMix = useMemo(() => {
    const mix = scopedProviders.reduce(
      (acc, provider) => {
        const label = providerKindLabel(provider.kind);
        acc[label] = (acc[label] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
    return Object.entries(mix)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
  }, [scopedProviders]);

  const physicalNoiseData = useMemo<PhysicalNoisePoint[]>(() => {
    if (!runTelemetry || !runTelemetry.noise_samples || runTelemetry.noise_samples.length === 0) {
      return [];
    }
    return runTelemetry.noise_samples.map((sample) => ({
      round: sample.index + 1,
      physicalErrorPct: Number((sample.physical_error_rate * 100).toFixed(3)),
      photonLossPct: Number((sample.photon_loss_rate * 100).toFixed(3)),
      displacementSigma: Number(sample.displacement_sigma.toFixed(4)),
    }));
  }, [runTelemetry]);
  const telemetryQueryLoading =
    !isMock &&
    (runTelemetryScientificQuery.isLoading ||
      (streamWarmupActive && runTelemetryWarmupQuery.isLoading));
  const physicalNoiseLoading =
    !systemOff && systemArmed && isApi && Boolean(activeRunId) && telemetryQueryLoading && !runTelemetry;
  const physicalNoiseError = runTelemetryHardError;

  const healthBadgeLabel = systemOff
    ? "Off"
    : !systemArmed
      ? "Standby"
    : isApi
      ? healthQuery.isError
        ? "API Error"
        : healthQuery.isLoading
          ? "Checking"
          : healthy
            ? "Operational"
            : "Degraded"
      : healthy
        ? "Operational"
        : "Checking";

  const healthBadgeClass = systemOff
    ? "badge badge-warning"
    : !systemArmed
      ? "badge"
    : isApi && healthQuery.isError
      ? "badge badge-warning"
      : `badge ${healthy ? "" : "badge-warning"}`;

  const { points: timelinePoints, stepMinutes } = timeRangeConfig(timeRangeFilter);
  const monitorTelemetrySourceAvailable = Boolean(
    runTelemetry &&
      (runTelemetry.noise_samples.length > 0 ||
        runTelemetry.syndrome_samples.length > 0 ||
        runTelemetry.decoder_interventions.length > 0),
  );
  const monitoringSynthetic = useMemo(
    () =>
      buildMonitoringSeries(
        activeDecoder,
        timelinePoints,
        stepMinutes,
        isMock,
        jobsCount,
        runsCount,
        providerCount,
      ),
    [activeDecoder, isMock, jobsCount, providerCount, runsCount, stepMinutes, timelinePoints],
  );

  const comparisonSynthetic = useMemo(
    () =>
      buildMonitoringSeries(
        compareDecoder,
        timelinePoints,
        stepMinutes,
        isMock,
        jobsCount,
        runsCount,
        providerCount,
      ),
    [compareDecoder, isMock, jobsCount, providerCount, runsCount, stepMinutes, timelinePoints],
  );

  const monitoringTelemetry = useMemo(
    () => buildMonitoringSeriesFromTelemetry(activeDecoder, runTelemetry, timelinePoints, stepMinutes),
    [activeDecoder, runTelemetry, stepMinutes, timelinePoints],
  );
  const comparisonTelemetry = useMemo(
    () => buildMonitoringSeriesFromTelemetry(compareDecoder, runTelemetry, timelinePoints, stepMinutes),
    [compareDecoder, runTelemetry, stepMinutes, timelinePoints],
  );

  const monitoringRaw = systemOff
    ? []
    : monitorTelemetrySourceAvailable
      ? monitoringTelemetry.series
      : isApi
        ? []
        : monitoringSynthetic;
  const comparisonRaw = systemOff
    ? []
    : monitorTelemetrySourceAvailable
      ? comparisonTelemetry.series
      : isApi
        ? []
        : comparisonSynthetic;
  const activeDecoderMissingTelemetry = monitorTelemetrySourceAvailable && !monitoringTelemetry.hasDecoderSignal;
  const compareDecoderMissingTelemetry =
    monitorTelemetrySourceAvailable && compareMode && !comparisonTelemetry.hasDecoderSignal;

  const monitoringPrimary = useMemo(() => downsampleSeries(monitoringRaw, 120), [monitoringRaw]);
  const monitoringCompare = useMemo(() => downsampleSeries(comparisonRaw, 120), [comparisonRaw]);
  const monitoringData = useMemo<MonitoringPointWithCompare[]>(() => {
    return monitoringPrimary.map((point, index) => ({
      ...point,
      compareNoise: monitoringCompare[index]?.noise ?? null,
      compareSuccess: monitoringCompare[index]?.success ?? null,
      compareError: monitoringCompare[index]?.error ?? null,
      compareLatency: monitoringCompare[index]?.latency ?? null,
    }));
  }, [monitoringCompare, monitoringPrimary]);
  const monitoringHasRows = monitoringData.length > 0;

  const activityFeed = useMemo(() => {
    const items: Array<{ tone: "green" | "red" | "blue"; text: string; time: string }> = [];

    if (isApi && anyApiError) {
      items.push({ tone: "red", text: "Backend API reported connectivity failures", time: "now" });
    } else {
      items.push({
        tone: "green",
        text: `${runsCount} runs tracked in current scope`,
        time: activeRun?.updated_at ? formatAgo(activeRun.updated_at) : "live",
      });
    }

    items.push({
      tone: providerCount > 0 ? "blue" : "red",
      text: `${providerCount} providers available for dispatch in filter`,
      time: formatAgo(latestProviderUpdate),
    });
    items.push({
      tone: queuedJobsCount > 0 ? "green" : "blue",
      text: `${queuedJobsCount} queued jobs in current scope`,
      time: formatAgo(latestJobUpdate),
    });

    return items;
  }, [
    anyApiError,
    isApi,
    latestJobUpdate,
    latestProviderUpdate,
    activeRun?.updated_at,
    providerCount,
    queuedJobsCount,
    runsCount,
  ]);

  const perValue = useMemo(() => {
    if (physicalNoiseData.length === 0) {
      return null;
    }
    const avg =
      physicalNoiseData.reduce((sum, point) => sum + point.physicalErrorPct, 0) / physicalNoiseData.length;
    return Number(avg.toFixed(4));
  }, [physicalNoiseData]);

  const latestRunMetrics = activeRun?.metrics ?? null;
  const previousRunMetrics = useMemo(() => {
    if (scopedRuns.length < 2) {
      return null;
    }
    if (!activeRunId) {
      return scopedRuns[scopedRuns.length - 2].metrics ?? null;
    }
    const activeIndex = scopedRuns.findIndex((run) => run.id === activeRunId);
    if (activeIndex === -1) {
      return scopedRuns[scopedRuns.length - 2].metrics ?? null;
    }
    if (activeIndex === 0) {
      return null;
    }
    return scopedRuns[activeIndex - 1].metrics ?? null;
  }, [activeRunId, scopedRuns]);
  const monitoringSplitIndex = Math.max(1, Math.floor(monitoringRaw.length / 2));
  const previousWindow = monitoringRaw.slice(0, monitoringSplitIndex);
  const currentWindow = monitoringRaw.slice(monitoringSplitIndex);

  const p95LatencyCurrent = percentile(
    currentWindow.map((point) => point.latency),
    95,
  );
  const p95LatencyPrevious = percentile(
    previousWindow.map((point) => point.latency),
    95,
  );
  const p95LatencyTrend = percentDelta(p95LatencyCurrent, p95LatencyPrevious);

  const throughputCurrent =
    average(currentWindow.map((point) => point.success / 100)) *
    (1000 / Math.max(1, average(currentWindow.map((point) => point.latency))));
  const throughputPrevious =
    average(previousWindow.map((point) => point.success / 100)) *
    (1000 / Math.max(1, average(previousWindow.map((point) => point.latency))));
  const throughputTrend = percentDelta(throughputCurrent, throughputPrevious);

  const queueAgedJobs = scopedJobs.filter((job) => job.status === "queued");
  const oldestQueuedAt = queueAgedJobs.reduce((oldest, job) => {
    const stamp = new Date(job.created_at).getTime();
    return Number.isFinite(stamp) && stamp < oldest ? stamp : oldest;
  }, Number.POSITIVE_INFINITY);
  const queueAgeMinutes =
    Number.isFinite(oldestQueuedAt) ? Math.max(0, (Date.now() - oldestQueuedAt) / 60_000) : 0;
  const queueAgeTrend = percentDelta(queueAgeMinutes, 5);

  const liveSyndromeSatisfactionRate = useMemo(() => {
    if (syndromeSamples.length === 0) {
      return null;
    }
    const triggered = syndromeSamples.filter((sample) => sample.is_triggered).length;
    const satisfied = 1 - triggered / Math.max(1, syndromeSamples.length);
    return clamp(satisfied, 0, 1);
  }, [syndromeSamples]);
  const syndromeCurrent =
    (latestRunMetrics?.syndrome_satisfaction_rate ?? liveSyndromeSatisfactionRate ?? 0) * 100;
  const syndromePrevious = (previousRunMetrics?.syndrome_satisfaction_rate ?? syndromeCurrent / 100) * 100;
  const syndromeTrend = percentDelta(syndromeCurrent, syndromePrevious);
  const dataUpdatedAt = runTelemetry?.updated_at ?? activeRun?.updated_at ?? healthData?.started_at ?? null;
  const confidenceScore = systemOff
    ? 0
    : clamp(((monitoringData.length + physicalNoiseData.length) / Math.max(1, timelinePoints + 40)) * 100, 6, 99);
  const globalRunLogicalErrorRate = latestRunMetrics?.logical_error_rate ?? null;
  const previousGlobalRunLogicalErrorRate = previousRunMetrics?.logical_error_rate ?? null;
  const globalRunLerTrend =
    globalRunLogicalErrorRate != null && previousGlobalRunLogicalErrorRate != null
      ? percentDelta(globalRunLogicalErrorRate, previousGlobalRunLogicalErrorRate)
      : 0;

  const scientificState = useMemo(
    () =>
      resolveScientificState({
        run: activeRun,
        telemetry: runTelemetryScientific,
        activeDecoder,
        validationPassed: Boolean(activeRun?.metrics?.scientific_validation_ready),
      }),
    [activeDecoder, activeRun, runTelemetryScientific],
  );
  const scientificExactnessLabel = scientificStateLabel(scientificState.state);
  const scientificExactnessClass = scientificStateStatusClass(scientificState.state);
  const scientificOverheadProviderKind = activeRun
    ? providerById.get(activeRun.provider_id)?.kind ?? null
    : null;
  const scientificZeroBaseline = scientificState.state === "IDLE";
  const scientificCardValues = useMemo<Record<ScientificCardKey, string>>(() => {
    if (scientificZeroBaseline) {
      return {
        ler: "0 / 0 = 0.0000%",
        per: "0 / 0 = 0.0000%",
        response_ratio: "0 / 0 = 0.000",
        rounds: "0",
        stabilizer_count: "0",
        syndrome_opportunities: "0",
        post_correction_overhead:
          scientificOverheadProviderKind === "photonic"
            ? "0 CV states / logical mode"
            : "0 physical qubits / logical qubit",
        residual_syndrome_rate: "0 / 0 = 0.0000%",
        request_line_count: "0",
        response_line_count: "0",
        expanded_shot_count: "0",
      };
    }
    return {
      ler: formatPercentWithCounts(
        scientificState.signals.logical_failures,
        scientificState.signals.logical_trials,
        4,
      ),
      per: formatPercentWithCounts(
        scientificState.signals.physical_error_events,
        scientificState.signals.physical_error_opportunities,
        4,
      ),
      response_ratio: formatRatioWithCounts(
        scientificState.signals.response_line_count,
        scientificState.signals.request_line_count,
        3,
      ),
      rounds: formatCount(scientificState.signals.rounds),
      stabilizer_count: formatCount(scientificState.signals.stabilizer_count),
      syndrome_opportunities: formatCount(scientificState.signals.syndrome_opportunities),
      post_correction_overhead: formatOverheadMapping(
        scientificState.signals.rounds,
        scientificState.signals.stabilizer_count,
        scientificOverheadProviderKind,
      ),
      residual_syndrome_rate: formatPercentWithCounts(
        scientificState.signals.residual_syndrome_events,
        scientificState.signals.syndrome_opportunities,
        4,
      ),
      request_line_count: formatCount(scientificState.signals.request_line_count),
      response_line_count: formatCount(scientificState.signals.response_line_count),
      expanded_shot_count: formatCompactCount(scientificState.signals.expanded_shot_count),
    };
  }, [scientificOverheadProviderKind, scientificState.signals, scientificZeroBaseline]);
  const scientificPrimaryCards = useMemo(
    () =>
      SCIENTIFIC_PRIMARY_CARD_ORDER.map((key) => ({
        key,
        contract: SCIENTIFIC_CARD_CONTRACTS[key],
        availability: scientificState.metricAvailability[key],
      })),
    [scientificState.metricAvailability],
  );
  const scientificSecondaryCards = useMemo(
    () =>
      SCIENTIFIC_SECONDARY_CARD_ORDER.map((key) => ({
        key,
        contract: SCIENTIFIC_CARD_CONTRACTS[key],
        availability: scientificState.metricAvailability[key],
      })),
    [scientificState.metricAvailability],
  );
  const scientificMissingPrimaryReasons = useMemo(
    () =>
      scientificPrimaryCards
        .filter((entry) => !entry.availability.available)
        .map(
          (entry) =>
            `${entry.contract.label} unavailable — ${entry.availability.availabilityReason}`,
        ),
    [scientificPrimaryCards],
  );
  const scientificMissingSignalsLabel = useMemo(() => {
    if (scientificState.state === "IDLE") {
      return "No active scientific context";
    }
    if (scientificState.completeness.missingSignals.length === 0) {
      return "No missing scientific signals";
    }
    return "Exact Calculation...";
  }, [scientificState.completeness.missingSignals.length, scientificState.state]);
  const scientificIngestingRows = useMemo(() => {
    const rows: Array<{ label: string; value: string }> = [];
    if (!scientificState.hasRunContext) {
      rows.push({ label: "Run", value: "No run selected" });
    } else {
      const runLabel = activeRun?.id ? activeRun.id.slice(0, 8).toUpperCase() : "active";
      rows.push({ label: "Run", value: `Run ${runLabel} detected` });
    }
    if (!scientificState.hasTelemetryContext) {
      rows.push({ label: "Telemetry", value: "Awaiting decoder output" });
    } else {
      rows.push({ label: "Telemetry", value: "Scientific telemetry stream connected" });
    }
    if (scientificState.signals.rounds != null) {
      rows.push({
        label: "Rounds",
        value: `${scientificState.signals.rounds.toLocaleString()} rounds detected`,
      });
    }
    if (scientificState.signals.stabilizer_count != null) {
      rows.push({
        label: "Stabilizers",
        value: `${scientificState.signals.stabilizer_count.toLocaleString()} stabilizers tracked`,
      });
    }
    if (scientificState.signals.request_line_count != null) {
      rows.push({
        label: "Request lines",
        value: scientificState.signals.request_line_count.toLocaleString(),
      });
    }
    if (scientificState.signals.response_line_count != null) {
      rows.push({
        label: "Response lines",
        value: scientificState.signals.response_line_count.toLocaleString(),
      });
    }
    return rows;
  }, [
    activeRun?.id,
    scientificState.hasRunContext,
    scientificState.hasTelemetryContext,
    scientificState.signals.request_line_count,
    scientificState.signals.response_line_count,
    scientificState.signals.rounds,
    scientificState.signals.stabilizer_count,
  ]);
  const scientificExactSourceRows =
    runTelemetryScientific?.decoder_exact_metrics ?? activeRun?.metrics?.decoder_exact_metrics ?? [];
  const scientificActiveDecoderRow = useMemo(
    () =>
      scientificExactSourceRows.find(
        (entry) => decoderRowMatchesActive(entry.decoder, activeDecoder) && entry.trials > 0,
      ) ?? null,
    [activeDecoder, scientificExactSourceRows],
  );

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }
    const availableSignals = (Object.keys(SCIENTIFIC_FIELD_LABELS) as ScientificField[]).filter(
      (field) => scientificState.signals[field] != null,
    );
    console.debug("[scientific-summary]", {
      selectedRunId: activeRunId,
      activeDecoder,
      activeDecoderExactRow: scientificActiveDecoderRow
        ? {
            decoder: scientificActiveDecoderRow.decoder,
            trials: scientificActiveDecoderRow.trials,
            logical_failures: scientificActiveDecoderRow.logical_failures,
          }
        : null,
      exactRowsInScope: scientificExactSourceRows.length,
      availableSignals,
      scientificState: scientificState.state,
      completenessPct: scientificState.completeness.percentage,
    });
  }, [
    activeDecoder,
    activeRunId,
    scientificActiveDecoderRow,
    scientificExactSourceRows.length,
    scientificState.completeness.percentage,
    scientificState.signals,
    scientificState.state,
  ]);

  const operationalKpiCards = useMemo<OperationalKpiCardModel[]>(() => {
    const cards: OperationalKpiCardModel[] = [
      {
        key: "p95-latency",
        label: "P95 Decoder Latency",
        value: `${p95LatencyCurrent.toFixed(1)} ms`,
        trendText: formatTrend(p95LatencyTrend),
        trendDelta: p95LatencyTrend,
        trendUpGood: false,
      },
      {
        key: "syndrome",
        label: "Syndrome Satisfaction",
        value: `${syndromeCurrent.toFixed(2)}%`,
        trendText: formatTrend(syndromeTrend),
        trendDelta: syndromeTrend,
        trendUpGood: true,
      },
      {
        key: "throughput",
        label: "Throughput",
        value: `${throughputCurrent.toFixed(2)} ops/s`,
        trendText: formatTrend(throughputTrend),
        trendDelta: throughputTrend,
        trendUpGood: true,
      },
      {
        key: "queue-age",
        label: "Queue Age",
        value: `${queueAgeMinutes.toFixed(1)} min`,
        trendText: formatTrend(queueAgeTrend),
        trendDelta: queueAgeTrend,
        trendUpGood: false,
      },
      {
        key: "confidence",
        label: "Confidence (Heuristic)",
        value: `${confidenceScore.toFixed(1)}%`,
        trendText: "Synthetic confidence from signal coverage",
        trendDelta: 0,
        trendUpGood: true,
      },
    ];

    if (globalRunLogicalErrorRate != null) {
      cards.push({
        key: "global-run-ler",
        label: "Global Run LER",
        value: `${(globalRunLogicalErrorRate * 100).toFixed(4)}%`,
        trendText:
          previousGlobalRunLogicalErrorRate != null
            ? `${formatTrend(globalRunLerTrend)} vs previous run`
            : "Legacy run.metrics.logical_error_rate scope",
        trendDelta: globalRunLerTrend,
        trendUpGood: false,
      });
    }
    return cards;
  }, [
    confidenceScore,
    globalRunLerTrend,
    globalRunLogicalErrorRate,
    p95LatencyCurrent,
    p95LatencyTrend,
    previousGlobalRunLogicalErrorRate,
    queueAgeMinutes,
    queueAgeTrend,
    syndromeCurrent,
    syndromeTrend,
    throughputCurrent,
    throughputTrend,
  ]);
  const anomalyThresholds = {
    noiseWarn: 0.022,
    noiseCritical: 0.03,
    successWarn: 95,
    errorWarn: 5,
    latencyWarn: 70,
    perWarn: 1.2,
  };

  const noiseAnomalies = monitoringData.filter((point) => point.noise >= anomalyThresholds.noiseWarn);
  const successAnomalies = monitoringData.filter((point) => point.success <= anomalyThresholds.successWarn);
  const errorAnomalies = monitoringData.filter((point) => point.error >= anomalyThresholds.errorWarn);
  const latencyAnomalies = monitoringData.filter((point) => point.latency >= anomalyThresholds.latencyWarn);
  const physicalAnomalies = physicalNoiseData.filter(
    (point) => point.physicalErrorPct >= anomalyThresholds.perWarn,
  );
  const latestPhysicalPoint =
    physicalNoiseData.length > 0 ? physicalNoiseData[physicalNoiseData.length - 1] : null;
  const physicalPctCeiling = Number(
    Math.max(
      1.4,
      Math.ceil(
        (Math.max(
          anomalyThresholds.perWarn,
          ...physicalNoiseData.map((point) => Math.max(point.physicalErrorPct, point.photonLossPct)),
        ) +
          0.1) *
          10,
      ) / 10,
    ).toFixed(1),
  );
  const physicalSigmaCeiling = Number(
    Math.max(
      0.18,
      Math.ceil((Math.max(0.01, ...physicalNoiseData.map((point) => point.displacementSigma)) + 0.01) * 20) / 20,
    ).toFixed(2),
  );
  const rawGkpOscillatorStates = runTelemetry?.gkp_oscillator_states ?? [];
  const latestSyndromeRound = useMemo(() => {
    if (syndromeSamples.length === 0) {
      return null;
    }
    return syndromeSamples.reduce((roundMax, sample) => Math.max(roundMax, sample.round), 0);
  }, [syndromeSamples]);
  const latestRoundSyndromes = useMemo<SyndromeSample[]>(() => {
    if (latestSyndromeRound === null) {
      return [];
    }
    return syndromeSamples.filter((sample) => sample.round === latestSyndromeRound);
  }, [latestSyndromeRound, syndromeSamples]);
  const syndromeExtractionActive = !systemOff && (activeSessionStreaming || activeRunStreaming);
  const streamingStatusClass = systemOff
    ? "status-failed"
    : syndromeExtractionActive
      ? "status-running"
      : "status-warning";
  const streamingStatusLabel = systemOff
    ? "Off"
    : syndromeExtractionActive
      ? activeIntegrationSession
        ? sessionStatusLabel(activeIntegrationSession.status)
        : "Streaming"
      : "Standby";
  const extractionStatusLabel = systemOff
    ? "Syndrome extraction off"
    : syndromeExtractionActive
      ? activeIntegrationSession
        ? `Syndrome extraction ${sessionStatusLabel(activeIntegrationSession.status).toLowerCase()}`
        : "Syndrome extraction live"
      : "Syndrome extraction ended";

  const qecLattice = useMemo<QecLatticeModel>(() => {
    const stabilizerCount = Math.min(64, outerCodeDistance * outerCodeDistance);
    const labelsFromSamples = Array.from(
      new Set(latestRoundSyndromes.map((sample) => sample.stabilizer)),
    ).sort((left, right) => {
      const rankDelta = stabilizerSortKey(left) - stabilizerSortKey(right);
      return rankDelta !== 0 ? rankDelta : left.localeCompare(right);
    });
    const labels = labelsFromSamples.length > 0 ? [...labelsFromSamples] : [];
    while (labels.length < stabilizerCount) {
      labels.push(stabilizerLabel(labels.length));
    }

    const columns = outerCodeDistance;
    const rows = outerCodeDistance;
    const width = 620;
    const height = 340;
    const padX = 56;
    const padY = 52;
    const stepX = columns > 1 ? (width - padX * 2) / (columns - 1) : 0;
    const stepY = rows > 1 ? (height - padY * 2) / (rows - 1) : 0;
    const sampleByLabel = new Map(
      latestRoundSyndromes.map((sample) => [sample.stabilizer, sample]),
    );

    const nodes: QecLatticeNode[] = labels.slice(0, stabilizerCount).map((label, index) => {
      const row = Math.floor(index / columns);
      const col = index % columns;
      const sample = sampleByLabel.get(label);
      return {
        key: label,
        label,
        x: Number((padX + col * stepX).toFixed(2)),
        y: Number((padY + row * stepY).toFixed(2)),
        triggered: sample?.is_triggered ?? false,
        value: sample?.value ?? 0,
      };
    });

    const edges: QecLatticeEdge[] = [];
    nodes.forEach((node, index) => {
      const row = Math.floor(index / columns);
      const col = index % columns;
      const rightIndex = index + 1;
      if (col < columns - 1 && rightIndex < nodes.length) {
        const right = nodes[rightIndex];
        edges.push({
          key: `${node.key}-${right.key}`,
          x1: node.x,
          y1: node.y,
          x2: right.x,
          y2: right.y,
        });
      }
      const downIndex = index + columns;
      if (row < rows - 1 && downIndex < nodes.length) {
        const down = nodes[downIndex];
        edges.push({
          key: `${node.key}-${down.key}`,
          x1: node.x,
          y1: node.y,
          x2: down.x,
          y2: down.y,
        });
      }
    });

    return {
      nodes,
      edges,
      columns,
      rows,
    };
  }, [latestRoundSyndromes, outerCodeDistance]);
  const qecTriggeredNodes = qecLattice.nodes.filter((node) => node.triggered);
  const qecPointerNodes = qecTriggeredNodes.slice(0, 8);
  const qecStabilizerTotal = Math.max(0, runTelemetry?.stabilizer_count ?? qecLattice.nodes.length);
  const qecTrackedTotal = qecLattice.nodes.length;
  const qecMapTrimmed = qecStabilizerTotal > qecTrackedTotal;
  const qecTriggeredPct =
    qecTrackedTotal > 0 ? (qecTriggeredNodes.length / Math.max(1, qecTrackedTotal)) * 100 : 0;
  const qecSurfaceDistance = outerCodeDistance;
  const qecSurfaceRoundLabel = latestSyndromeRound !== null ? `Round ${latestSyndromeRound + 1}` : "No round";
  const gkpOscillatorStates = useMemo<GkpOscillatorStateSample[]>(() => {
    if (rawGkpOscillatorStates.length > 0) {
      return rawGkpOscillatorStates;
    }
    if (physicalNoiseData.length === 0) {
      return [];
    }
    const sliced = physicalNoiseData.slice(-Math.min(48, physicalNoiseData.length));
    return sliced.map((point, index) => {
      const angle = index * 0.58 + point.round * 0.12;
      const radius = clamp(point.displacementSigma * 3.2, 0.16, 1.25);
      const q = Number((radius * Math.cos(angle)).toFixed(4));
      const p = Number((radius * Math.sin(angle)).toFixed(4));
      const variance = Number((0.03 + point.displacementSigma * 0.24).toFixed(4));
      const energy = Number((point.photonLossPct / 9).toFixed(4));
      return {
        round: point.round - 1,
        mode: `M${((index % 12) + 1).toString().padStart(2, "0")}`,
        q,
        p,
        variance,
        energy,
        flagged: point.physicalErrorPct >= anomalyThresholds.perWarn || point.photonLossPct >= 1.1,
      };
    });
  }, [anomalyThresholds.perWarn, physicalNoiseData, rawGkpOscillatorStates]);
  const gkpOscillatorFallback = rawGkpOscillatorStates.length === 0 && gkpOscillatorStates.length > 0;
  const gkpAxisLimit = useMemo(() => {
    if (gkpOscillatorStates.length === 0) {
      return 1;
    }
    const maxAbs = gkpOscillatorStates.reduce(
      (currentMax, sample) => Math.max(currentMax, Math.abs(sample.q), Math.abs(sample.p)),
      0,
    );
    return Math.max(0.95, Math.min(1.8, Math.ceil(maxAbs * 10) / 10));
  }, [gkpOscillatorStates]);
  const gkpOscillatorMapPoints = useMemo<GkpOscillatorMapPoint[]>(() => {
    if (gkpOscillatorStates.length === 0) {
      return [];
    }
    const width = 620;
    const height = 340;
    const centerX = width / 2;
    const centerY = height / 2;
    const scaleX = 240;
    const scaleY = 124;
    return gkpOscillatorStates.slice(-180).map((sample, index) => {
      const x = Number((centerX + (sample.q / gkpAxisLimit) * scaleX).toFixed(2));
      const y = Number((centerY - (sample.p / gkpAxisLimit) * scaleY).toFixed(2));
      return {
        key: `${sample.round}-${sample.mode}-${index}`,
        mode: sample.mode,
        round: sample.round,
        q: sample.q,
        p: sample.p,
        variance: sample.variance ?? 0,
        energy: sample.energy ?? 0,
        flagged: sample.flagged ?? false,
        x,
        y,
      };
    });
  }, [gkpAxisLimit, gkpOscillatorStates]);
  const gkpFlaggedPoints = gkpOscillatorMapPoints.filter((point) => point.flagged);
  const gkpPointerPoints = gkpFlaggedPoints.slice(0, 10);
  const gkpModesTracked = new Set(gkpOscillatorMapPoints.map((point) => point.mode)).size;
  const gkpLatestRound = gkpOscillatorStates.reduce((roundMax, sample) => Math.max(roundMax, sample.round), -1);
  const gkpRoundLabel = gkpLatestRound >= 0 ? `Round ${gkpLatestRound + 1}` : "No round";
  const gkpVarianceAvg =
    gkpOscillatorMapPoints.length > 0
      ? average(gkpOscillatorMapPoints.map((point) => point.variance))
      : 0;
  const gkpEnergyAvg =
    gkpOscillatorMapPoints.length > 0 ? average(gkpOscillatorMapPoints.map((point) => point.energy)) : 0;
  const qecMapHeading =
    encodingMapMode === "surface"
      ? "Surface Syndrome Map (Outer Code)"
      : "Raw GKP Oscillator Map (Inner Code)";
  const qecMapSubtitle =
    encodingMapMode === "surface"
      ? `Surface lattice telemetry for ${qecSurfaceRoundLabel} · distance-${qecSurfaceDistance}`
      : gkpOscillatorFallback
        ? `Derived oscillator projection for ${gkpRoundLabel} from physical noise telemetry`
        : `Direct oscillator telemetry for ${gkpRoundLabel} with phase-space state vectors`;
  const opsInterventionSeries = useMemo(() => {
    const rows = (runTelemetry?.decoder_interventions ?? []).slice(-32);
    if (rows.length === 0) {
      return Array.from({ length: 12 }, (_, index) => ({
        key: `idle-${index}`,
        roundLabel: `R${index + 1}`,
        totalFlips: 0,
        totalResidual: 0,
        loadIndex: 0,
        round: null as number | null,
      }));
    }
    const byRound = new Map<number, { flips: number; residual: number }>();
    rows.forEach((row) => {
      const current = byRound.get(row.round) ?? { flips: 0, residual: 0 };
      current.flips += row.flips;
      current.residual += row.residual_weight;
      byRound.set(row.round, current);
    });
    const ordered = Array.from(byRound.entries())
      .sort((left, right) => left[0] - right[0])
      .slice(-12);
    const peak = Math.max(1, ...ordered.map(([, value]) => value.flips + value.residual * 1.4));
    return ordered.map(([round, value]) => {
      const combined = value.flips + value.residual * 1.4;
      return {
        key: `round-${round}`,
        roundLabel: `R${round + 1}`,
        totalFlips: Number(value.flips.toFixed(2)),
        totalResidual: Number(value.residual.toFixed(2)),
        loadIndex: Number(((combined / peak) * 100).toFixed(1)),
        round,
      };
    });
  }, [runTelemetry?.decoder_interventions]);
  const latestInterventionRoundLabel = useMemo(() => {
    const latest = opsInterventionSeries[opsInterventionSeries.length - 1];
    if (!latest || latest.round === null) {
      return "idle";
    }
    return `R${latest.round + 1}`;
  }, [opsInterventionSeries]);
  const opsRawEvents = useMemo(() => {
    if (systemOff) {
      return [
        {
          level: "warn" as const,
          text: "System off: telemetry and decoder stream halted.",
          tag: "off",
          source: "system" as const,
        },
      ];
    }
    const events: Array<{
      level: "info" | "warn" | "critical" | "ok";
      text: string;
      tag: string;
      source: "decoder" | "physical" | "scope" | "system";
    }> = [];

    if (activeIntegrationSession) {
      events.push({
        level: sessionStatusLevel(activeIntegrationSession.status),
        text: `Session #${activeIntegrationSession.id.slice(0, 8).toUpperCase()} ${sessionStatusLabel(
          activeIntegrationSession.status,
        )} (${activeIntegrationSession.adapter_id})`,
        tag: `${activeIntegrationSession.provider.toUpperCase()} · ${formatAgo(
          activeIntegrationSession.updated_at,
        )}`,
        source: "system",
      });
    }

    (sessionLogsQuery.data?.lines ?? []).slice(-30).forEach((entry) => {
      events.push({
        level: inferLogLevel(entry.stream, entry.line),
        text: entry.line.trim() || "(empty line)",
        tag: `${entry.stream.toUpperCase()} · ${formatClock(entry.timestamp)}`,
        source: "system",
      });
    });

    (runTelemetry?.decoder_interventions ?? [])
      .slice(-28)
      .forEach((row) => {
        const decoder = decoderLabel(parseDecoderKey(row.decoder) ?? activeDecoder);
        const level = row.residual_weight >= 4 ? "warn" : "ok";
        events.push({
          level,
          text: `Round ${row.round + 1}: ${decoder} flips=${row.flips}, residual=${row.residual_weight}`,
          tag: `R${row.round + 1}`,
          source: "decoder",
        });
      });

    physicalAnomalies.slice(-8).forEach((point) => {
      events.push({
        level: "critical",
        text: `Physical anomaly at round ${point.round}: PER ${point.physicalErrorPct.toFixed(3)}%`,
        tag: "PER",
        source: "physical",
      });
    });

    activityFeed.forEach((item) => {
      events.push({
        level: item.tone === "red" ? "critical" : item.tone === "blue" ? "info" : "ok",
        text: item.text,
        tag: item.time,
        source: "scope",
      });
    });

    if (events.length === 0) {
      events.push({
        level: "info",
        text: "Waiting for decoder telemetry stream...",
        tag: "idle",
        source: "system",
      });
    }
    return events.slice(-60);
  }, [
    activeDecoder,
    activeIntegrationSession,
    activityFeed,
    physicalAnomalies,
    runTelemetry?.decoder_interventions,
    sessionLogsQuery.data?.lines,
    systemOff,
  ]);
  const opsLiveEvents = useMemo(() => {
    const maxRows = Math.min(12, opsRawEvents.length);
    if (maxRows === 0) {
      return [];
    }
    return Array.from({ length: maxRows }, (_, index) => {
      const offset = (opsLogCursor + index) % opsRawEvents.length;
      const event = opsRawEvents[offset];
      return {
        ...event,
        id: `${event.source}-${event.tag}-${offset}-${index}`,
      };
    });
  }, [opsLogCursor, opsRawEvents]);

  useEffect(() => {
    if (opsRawEvents.length <= 1) {
      return;
    }
    const delay = syndromeExtractionActive ? 900 : 1700;
    const timer = window.setInterval(() => {
      setOpsLogCursor((current) => (current + 1) % opsRawEvents.length);
    }, delay);
    return () => window.clearInterval(timer);
  }, [opsRawEvents.length, syndromeExtractionActive]);

  const compareDelta = useMemo(() => {
    if (!compareMode) {
      return 0;
    }
    const primaryValues = monitoringData.map((point) => metricValue(point, activeChart, false));
    const compareValues = monitoringData.map((point) => metricValue(point, activeChart, true));
    return percentDelta(average(primaryValues), average(compareValues));
  }, [activeChart, compareMode, monitoringData]);
  const compareHigherIsBetter = activeChart === "success";
  const compareIsGood = compareHigherIsBetter ? compareDelta >= 0 : compareDelta <= 0;

  const workflowAlerts = useMemo<WorkflowAlertItem[]>(() => {
    const items: WorkflowAlertItem[] = [];
    if (anyApiError) {
      items.push({
        id: "api-link",
        level: "critical",
        title: "Backend Connectivity",
        detail: "One or more API endpoints are unreachable in live mode.",
        metric: "API health",
      });
    }
    if (latencyAnomalies.length > 0) {
      items.push({
        id: "latency-spike",
        level: "warning",
        title: "Latency threshold breached",
        detail: `${latencyAnomalies.length} windows above ${anomalyThresholds.latencyWarn} ms`,
        metric: `P95 ${p95LatencyCurrent.toFixed(1)} ms`,
      });
    }
    if (errorAnomalies.length > 0) {
      items.push({
        id: "error-rise",
        level: "warning",
        title: "Decoder error rate elevated",
        detail: `${errorAnomalies.length} windows above ${anomalyThresholds.errorWarn}%`,
        metric: `${average(errorAnomalies.map((point) => point.error)).toFixed(2)}% avg`,
      });
    }
    if (perValue !== null && perValue >= anomalyThresholds.perWarn) {
      items.push({
        id: "per-high",
        level: "critical",
        title: "Physical error rate high",
        detail: `PER exceeded ${anomalyThresholds.perWarn.toFixed(1)}% threshold`,
        metric: `${perValue.toFixed(3)}%`,
      });
    }
    if (items.length === 0) {
      items.push({
        id: "all-clear",
        level: "info",
        title: "No critical anomalies",
        detail: "All monitored bands are within configured thresholds.",
        metric: "Operational",
      });
    }
    return items;
  }, [
    anomalyThresholds.errorWarn,
    anomalyThresholds.latencyWarn,
    anomalyThresholds.perWarn,
    anyApiError,
    errorAnomalies,
    latencyAnomalies,
    p95LatencyCurrent,
    perValue,
  ]);

  const updateWorkflowState = (alertId: string, patch: Partial<AlertWorkflowState>) => {
    setAlertWorkflow((current) => {
      const previous = current[alertId] ?? {
        acknowledged: false,
        owner: "Unassigned",
        notes: "",
      };
      return {
        ...current,
        [alertId]: {
          ...previous,
          ...patch,
        },
      };
    });
  };

  const activeProviderName =
    providerFilter !== "all"
      ? providerById.get(providerFilter)?.name ?? "Unknown Provider"
      : "All Providers";
  const activeRunProvider = activeRun ? providerById.get(activeRun.provider_id) ?? null : null;
  const heroProviderLabel = activeRunProvider?.name ?? activeProviderName;
  const heroHardwareLabel = activeRunProvider
    ? providerKindLabel(activeRunProvider.kind)
    : "Mixed Hardware Scope";
  const activeRunShortId = activeRunId ? activeRunId.slice(0, 8).toUpperCase() : "None";
  const activeSessionShortId = activeIntegrationSession
    ? activeIntegrationSession.id.slice(0, 8).toUpperCase()
    : "None";
  const quickLaunchBusy = createRunMutation.isPending || createSessionMutation.isPending;
  const sessionStopBusy = stopSessionMutation.isPending;
  const launchProviderFamily = launchProvider ? resolveProviderFamily(launchProvider) : "unknown";
  const quickLaunchRequiresNeuralModel =
    launchProvider != null &&
    activeDecoder === "neural_mwpm" &&
    familyRequiresNeuralModel(launchProviderFamily);
  const quickLaunchMissingNeuralModel = quickLaunchRequiresNeuralModel && !neuralModelPath.trim();
  const replaySourceOptions = useMemo<ReplaySourceOption[]>(() => {
    return [...scopedRuns]
      .filter((run) => run.status === "finished")
      .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime())
      .map((run) => ({
        runId: run.id,
        datasetLabel: run.dataset_label,
        providerName: providerById.get(run.provider_id)?.name ?? run.provider_id,
        updatedAtLabel: formatAgo(run.updated_at),
      }));
  }, [providerById, scopedRuns]);
  useEffect(() => {
    if (replaySourceOptions.length === 0) {
      if (replaySourceRunId !== "") {
        setReplaySourceRunId("");
      }
      return;
    }
    if (!replaySourceRunId || !replaySourceOptions.some((source) => source.runId === replaySourceRunId)) {
      setReplaySourceRunId(replaySourceOptions[0].runId);
    }
  }, [replaySourceOptions, replaySourceRunId]);
  const selectedReplaySourceRun = useMemo(
    () => (replaySourceRunId ? runById.get(replaySourceRunId) ?? null : null),
    [replaySourceRunId, runById],
  );
  const replayLaunchProvider = selectedReplaySourceRun
    ? providerById.get(selectedReplaySourceRun.provider_id) ?? null
    : launchProvider;
  const replayLaunchProviderFamily = replayLaunchProvider ? resolveProviderFamily(replayLaunchProvider) : "unknown";
  const benchmarkIncludesNeural = benchmarkDecoders.includes("neural_mwpm");
  const benchmarkRequiresNeuralModel =
    launchProvider != null &&
    benchmarkIncludesNeural &&
    familyRequiresNeuralModel(launchProviderFamily);
  const providerOperationalStateText = !launchProvider
    ? "No provider configured"
    : !providerReady(launchProvider)
      ? "Provider configured but currently offline"
      : scientificTransport(launchProvider) != null
        ? "Provider available and scientific-ready"
        : "Provider configured but scientific mode unsupported";
  const baseSessionUnavailableReason =
    !isApi
      ? "Scientific session unavailable — switch to Live API mode"
      : systemOff
        ? "Scientific session unavailable — system is off"
        : anyApiError
          ? "Scientific session unavailable — backend unreachable"
          : launchProvider == null
            ? "Scientific session unavailable — no provider configured"
            : !providerReady(launchProvider)
              ? "Scientific session unavailable — provider configured but offline"
              : !launchProvider.supports_scientific
                ? "Scientific session unavailable — provider configured but scientific mode unsupported"
                : scientificTransport(launchProvider) == null
                  ? "Scientific session unavailable — provider configured but live mode unsupported"
                  : launchProviderFamily === "unknown"
                    ? "Scientific session unavailable — provider configured but adapter mapping missing"
                    : null;
  const benchmarkBaseUnavailableReason =
    !isApi
      ? "Benchmark unavailable — switch to Live API mode"
      : systemOff
        ? "Benchmark unavailable — system is off"
        : anyApiError
          ? "Benchmark unavailable — backend unreachable"
          : launchProvider == null
            ? "Benchmark unavailable — no provider configured"
            : !providerReady(launchProvider)
              ? "Benchmark unavailable — provider configured but offline"
              : !launchProvider.supports_benchmark
                ? "Benchmark unavailable — provider configured but benchmark mode unsupported"
                : scientificTransport(launchProvider) == null
                  ? "Benchmark unavailable — provider configured but live mode unsupported"
                  : launchProviderFamily === "unknown"
                    ? "Benchmark unavailable — provider configured but adapter mapping missing"
                    : null;
  const replayBaseUnavailableReason =
    !isApi
      ? "Replay unavailable — switch to Live API mode"
      : systemOff
        ? "Replay unavailable — system is off"
        : anyApiError
          ? "Replay unavailable — backend unreachable"
          : replayLaunchProvider == null
            ? "Replay unavailable — no provider configured"
            : !providerReady(replayLaunchProvider)
              ? "Replay unavailable — provider configured but offline"
              : !replayLaunchProvider.supports_replay
                ? "Replay unavailable — provider configured but replay mode unsupported"
                : replayLaunchProviderFamily === "unknown"
                  ? "Replay unavailable — provider configured but adapter mapping missing"
                  : null;
  const scientificSessionUnavailableReason =
    baseSessionUnavailableReason ??
    (quickLaunchMissingNeuralModel
      ? "Scientific session unavailable — set Neural Model path for Neural MWPM replay sessions"
      : null);
  const benchmarkMenuDisabledReason =
    benchmarkBaseUnavailableReason ??
    (benchmarkRequiresNeuralModel && !neuralModelPath.trim()
      ? "Benchmark unavailable — set Neural Model path for Neural MWPM replay sessions"
      : null);
  const benchmarkSessionUnavailableReason =
    benchmarkMenuDisabledReason ??
    (benchmarkDecoders.length === 0 ? "Benchmark unavailable — select at least one decoder" : null);
  const replaySessionUnavailableReason =
    replayBaseUnavailableReason ??
    (replaySourceOptions.length === 0
      ? providersData.length > 0
        ? "Replay unavailable — provider configured but no replay source available"
        : "Replay unavailable — no historical run in scope"
      : null) ??
    (!selectedReplaySourceRun ? "Replay unavailable — select a replay source" : null);
  const sessionRunning = activeSessionStreaming;
  const launcherStatus = sessionStopBusy
    ? "stopping"
    : quickLaunchBusy || sessionControlState.status === "launching"
      ? "launching"
      : sessionRunning
        ? "running"
        : sessionControlState.status === "failed"
          ? "failed"
          : "idle";
  const drilldownProviderName = activeRun
    ? providerById.get(activeRun.provider_id)?.name ?? activeRun.provider_id
    : activeProviderName;

  const queueIbmApiKeyLaunch = (input: LaunchSessionInput) => {
    setPendingIbmLaunch(input);
    setIbmApiKeyInput("");
    setIbmLiveSourceMode(input.ibmLiveSourceMode ?? "metadata");
    setIbmInstanceInput(input.ibmInstance ?? "");
    setIbmApiKeyError(null);
    setIbmApiKeyDialogOpen(true);
    setSessionLauncherMenuOpen(false);
    setBenchmarkDialogOpen(false);
    setReplayDialogOpen(false);
    setQuickLaunchTone("info");
    setQuickLaunchMessage("Enter IBM API key to start IBM live session.");
  };

  const closeIbmApiKeyDialog = () => {
    if (setIbmApiKeyMutation.isPending) {
      return;
    }
    setIbmApiKeyDialogOpen(false);
    setPendingIbmLaunch(null);
    setIbmApiKeyInput("");
    setIbmApiKeyError(null);
  };

  const launchSession = async (input: LaunchSessionInput) => {
    if (systemOff) {
      setSystemOff(false);
    }
    armSystem();
    clearError();
    beginLaunch(input.mode);
    setSessionLauncherMenuOpen(false);
    setBenchmarkDialogOpen(false);
    setReplayDialogOpen(false);
    setActiveHomeSessionSnapshot(null);
    homeSessionStatusRef.current = null;
    const primaryDecoder = input.decoders[0] ?? activeDecoder;
    const launchPlan = buildQuickLaunchPlan(input.provider, primaryDecoder, neuralModelPath, input.mode);
    const launchProviderFamily = resolveProviderFamily(input.provider);
    const launchWorkflowId = workflowForProviderFamily(launchProviderFamily);
    const launchDecoders = input.decoders.length > 0 ? input.decoders : [activeDecoder];
    const launchDecoderLabel = launchDecoders.map((decoder) => decoderLabel(decoder)).join(", ");
    if (!launchPlan) {
      const unsupportedMessage =
        input.mode === "replay"
          ? "Replay unavailable — provider configured but replay mode unsupported"
          : "Session unavailable — provider configured but live mode unsupported";
      markFailed(unsupportedMessage);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(unsupportedMessage);
      return;
    }
    if (
      adapterRequiresNeuralModel(launchPlan.adapterId) &&
      launchDecoders.includes("neural_mwpm") &&
      !neuralModelPath.trim()
    ) {
      markFailed("Set Neural Model path before running neural_mwpm in replay mode.");
      setQuickLaunchTone("error");
      setQuickLaunchMessage("Set Neural Model path before running neural_mwpm in replay mode.");
      return;
    }
    const timestamp = new Date().toISOString().replace("T", " ").slice(0, 19);
    const modeLabel =
      input.mode === "scientific"
        ? "scientific"
        : input.mode === "benchmark"
          ? "benchmark"
          : "replay";
    const sourceLabel = input.runSource ? ` from ${input.runSource.id.slice(0, 8).toUpperCase()}` : "";
    const circuitLabel = input.circuitDesign ? ` using ${input.circuitDesign.name}` : "";
    setQuickLaunchTone("info");
    setQuickLaunchMessage(
      `Starting ${input.provider.name} ${modeLabel} session${sourceLabel} with ${launchDecoderLabel}${circuitLabel}...`,
    );
    setActiveContext({ runId: null, sessionId: null, mode: input.mode });
    let createdRunId: string | null = null;

    try {
      const run = await createRunMutation.mutateAsync({
        workflow_id: launchWorkflowId,
        provider_id: input.provider.id,
        dataset_label: `${input.provider.name} ${input.datasetHint} ${modeLabel}${sourceLabel} ${timestamp}`,
        decoders: launchDecoders,
      });
      createdRunId = run.id;
      setActiveContext({ runId: run.id, sessionId: null, mode: input.mode });
      const allowCircuitDesignConfig = input.circuitDesign && supportsSoftwareCircuitDesign(input.provider);
      const circuitDesign = allowCircuitDesignConfig ? input.circuitDesign : null;
      const circuitConfig = circuitDesign
        ? {
            circuit_name: circuitDesign.name,
            circuit_qasm: circuitDesign.qasm,
            circuit_qubits: circuitDesign.qubitCount,
            circuit_depth: circuitDesign.depth,
            circuit_gate_count: circuitDesign.gateCount,
            circuit_hardware_target: circuitDesign.hardwareTarget,
            circuit_detector_model: circuitDesign.compileArtifact.photonic_detector_model,
            circuit_noise_config: JSON.stringify(circuitDesign.noiseConfig),
            circuit_compile_artifact: JSON.stringify(circuitDesign.compileArtifact),
            circuit_calibration_snapshot:
              circuitDesign.calibrationSnapshotId ?? circuitDesign.compileArtifact.calibration_snapshot_id,
            simulator_shots: 16384,
            circuit_gate_plan: JSON.stringify(
              circuitDesign.operations.map((operation) => ({
                gate: operation.gate,
                target: operation.target,
                control: operation.control ?? null,
                parameter: operation.parameter ?? null,
              })),
            ),
          }
        : {};
      const session = await createSessionMutation.mutateAsync({
        run_id: run.id,
        adapter_id: launchPlan.adapterId,
        config: {
          ...launchPlan.config,
          mode: input.mode,
          provider_scope: providerFilter,
          time_range: timeRangeFilter,
          run_source: input.runSource?.id,
          compare_decoders: input.mode === "benchmark" ? launchDecoders : undefined,
          skip_replay: input.mode === "replay" ? false : launchPlan.config.skip_replay,
          ...circuitConfig,
          ...(launchPlan.adapterId === "ibm_superconducting_live"
            ? {
                ibm_live_source_mode: input.ibmLiveSourceMode ?? "metadata",
                ibm_instance:
                  input.ibmInstance && input.ibmInstance.trim().length > 0
                    ? input.ibmInstance.trim()
                    : undefined,
              }
            : {}),
        },
      });
      markRunning({ runId: run.id, sessionId: session.id, mode: input.mode });
      setActiveHomeSessionSnapshot(session);
      setOpsLogCursor(0);
      setQuickLaunchTone("success");
      setQuickLaunchMessage(
        `Session #${session.id.slice(0, 8).toUpperCase()} started for ${input.provider.name} (${launchDecoderLabel})${circuitLabel}.`,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        markFailed("Integration session endpoint is unavailable.");
        setQuickLaunchTone("error");
        setQuickLaunchMessage(
          "Integration session endpoint is unavailable. Restart backend from the latest source.",
        );
        setActiveHomeSessionSnapshot(null);
        return;
      }
      const message = error instanceof Error ? error.message : "Failed to start session.";
      markFailed(message);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(message);
      setActiveContext({ runId: createdRunId, sessionId: null, mode: input.mode });
      setActiveHomeSessionSnapshot(null);
    }
  };

  const launchSessionWithProviderPrompt = async (input: LaunchSessionInput) => {
    const providerFamily = resolveProviderFamily(input.provider);
    if (providerFamily === "ibm" && (input.mode === "scientific" || input.mode === "benchmark")) {
      queueIbmApiKeyLaunch(input);
      return;
    }
    await launchSession(input);
  };

  const handleConfirmIbmApiKeyAndLaunch = async () => {
    if (!pendingIbmLaunch) {
      setIbmApiKeyDialogOpen(false);
      return;
    }
    const trimmedKey = ibmApiKeyInput.trim();
    if (!trimmedKey) {
      const message = "IBM API key is required to start IBM live sessions.";
      setIbmApiKeyError(message);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(message);
      return;
    }
    const trimmedInstance = ibmInstanceInput.trim();
    try {
      setIbmApiKeyError(null);
      await setIbmApiKeyMutation.mutateAsync({ api_key: trimmedKey });
      const queuedLaunch = {
        ...pendingIbmLaunch,
        ibmLiveSourceMode,
        ibmInstance: trimmedInstance || undefined,
      };
      setPendingIbmLaunch(null);
      setIbmApiKeyDialogOpen(false);
      setIbmApiKeyInput("");
      setQuickLaunchTone("info");
      setQuickLaunchMessage("IBM API key stored. Starting session...");
      await launchSession(queuedLaunch);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to store IBM API key.";
      setIbmApiKeyError(message);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(message);
    }
  };

  const openCircuitDesignDialogForLaunch = (input: LaunchSessionInput) => {
    setPendingCircuitLaunch(input);
    setCircuitDesignDialogOpen(true);
    setSessionLauncherMenuOpen(false);
    setBenchmarkDialogOpen(false);
    setReplayDialogOpen(false);
  };

  const closeCircuitDesignDialog = () => {
    if (quickLaunchBusy) {
      return;
    }
    setCircuitDesignDialogOpen(false);
    setPendingCircuitLaunch(null);
  };

  const handleStartSessionFromCircuitDesign = async (circuitDesign: CircuitDesignDraft) => {
    if (!pendingCircuitLaunch) {
      return;
    }
    const launchInput: LaunchSessionInput = {
      ...pendingCircuitLaunch,
      circuitDesign,
      datasetHint: `${pendingCircuitLaunch.datasetHint} ${circuitDesign.name}`,
    };
    setCircuitDesignDialogOpen(false);
    setPendingCircuitLaunch(null);
    await launchSessionWithProviderPrompt(launchInput);
  };

  const handleStartScientificSession = async () => {
    if (scientificSessionUnavailableReason) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage(scientificSessionUnavailableReason);
      return;
    }
    if (!launchProvider) {
      return;
    }
    const launchInput: LaunchSessionInput = {
      mode: "scientific",
      provider: launchProvider,
      decoders: [activeDecoder],
      datasetHint: `scientific ${timeRangeFilter} ${activeDecoder}`,
    };
    if (supportsSoftwareCircuitDesign(launchProvider)) {
      openCircuitDesignDialogForLaunch(launchInput);
      return;
    }
    await launchSessionWithProviderPrompt(launchInput);
  };

  const handleStartBenchmarkSession = async () => {
    if (benchmarkSessionUnavailableReason) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage(benchmarkSessionUnavailableReason);
      return;
    }
    if (!launchProvider || benchmarkDecoders.length === 0) {
      return;
    }
    await launchSessionWithProviderPrompt({
      mode: "benchmark",
      provider: launchProvider,
      decoders: benchmarkDecoders,
      datasetHint: `benchmark ${timeRangeFilter}`,
    });
  };

  const handleStartReplaySession = async () => {
    if (replaySessionUnavailableReason) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage(replaySessionUnavailableReason);
      return;
    }
    if (!selectedReplaySourceRun) {
      return;
    }
    const sourceProvider = providerById.get(selectedReplaySourceRun.provider_id);
    if (!sourceProvider) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage("Replay unavailable — source provider is no longer configured.");
      return;
    }
    if (!providerReady(sourceProvider)) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage("Replay unavailable — source provider is offline.");
      return;
    }
    if (!sourceProvider.supports_replay) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage("Replay unavailable — source provider does not support replay mode.");
      return;
    }
    await launchSession({
      mode: "replay",
      provider: sourceProvider,
      decoders: selectedReplaySourceRun.decoders.length > 0
        ? (selectedReplaySourceRun.decoders
            .map((decoder) => parseDecoderKey(decoder))
            .filter((decoder): decoder is DecoderKey => decoder !== null))
        : [activeDecoder],
      datasetHint: `replay source ${selectedReplaySourceRun.id.slice(0, 8).toUpperCase()}`,
      runSource: selectedReplaySourceRun,
    });
  };

  const handleStopSession = async () => {
    const sessionId = activeIntegrationSession?.id ?? activeHomeSessionId;
    if (!sessionId) {
      setQuickLaunchTone("error");
      setQuickLaunchMessage("No active session to stop.");
      return;
    }
    markStopping();
    setQuickLaunchTone("info");
    setQuickLaunchMessage(`Stopping session #${sessionId.slice(0, 8).toUpperCase()}...`);
    try {
      await stopSessionMutation.mutateAsync(sessionId);
      markStopped({ preserveRun: true });
      setActiveHomeSessionSnapshot(null);
      homeSessionStatusRef.current = null;
      setQuickLaunchTone("info");
      setQuickLaunchMessage(`Session #${sessionId.slice(0, 8).toUpperCase()} stopped.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to stop active session.";
      markFailed(message);
      setQuickLaunchTone("error");
      setQuickLaunchMessage(message);
    }
  };
  const handleToggleBenchmarkDecoder = (decoder: DecoderKey) => {
    setBenchmarkDecoders((current) =>
      current.includes(decoder)
        ? current.filter((value) => value !== decoder)
        : [...current, decoder],
    );
  };
  const handleOpenBenchmarkDialog = () => {
    setSessionLauncherMenuOpen(false);
    setBenchmarkDialogOpen(true);
  };
  const handleOpenReplayDialog = () => {
    setSessionLauncherMenuOpen(false);
    setReplayDialogOpen(true);
  };
  const handleViewRun = () => {
    if (!activeRunId) {
      return;
    }
    navigate("/runs");
  };
  const handleOpenTelemetryForRun = () => {
    if (!activeRunId) {
      return;
    }
    navigate(`/decoder/telemetry?runA=${encodeURIComponent(activeRunId)}&compare=0`);
  };
  const handleOpenValidationForRun = () => {
    if (!activeRunId) {
      return;
    }
    navigate(`/decoder/validation?run=${encodeURIComponent(activeRunId)}`);
  };

  const handleSystemOff = async () => {
    if (systemOff) {
      setSystemOff(false);
      setQuickLaunchTone("info");
      setQuickLaunchMessage("System turned on in standby. Select a provider and start a run to populate metrics.");
      return;
    }

    setSystemOff(true);
    setDrilldown(null);
    setOpsLogCursor(0);
    setSessionLauncherMenuOpen(false);
    setCircuitDesignDialogOpen(false);
    setPendingCircuitLaunch(null);
    setBenchmarkDialogOpen(false);
    setReplayDialogOpen(false);
    markStopped();
    setActiveContext({ runId: null, sessionId: null, mode: null });
    setActiveHomeSessionSnapshot(null);
    homeSessionStatusRef.current = null;
    setQuickLaunchTone("info");
    const sessionId = activeIntegrationSession?.id ?? activeHomeSessionId;
    if (apiEnabled && sessionId) {
      try {
        await stopSessionMutation.mutateAsync(sessionId);
        setQuickLaunchMessage(
          `System switched off. Session #${sessionId.slice(0, 8).toUpperCase()} stopped and metrics reset to zero.`,
        );
        return;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to stop active session while powering off.";
        setQuickLaunchTone("error");
        setQuickLaunchMessage(`System switched off, but session stop failed: ${message}`);
        return;
      }
    }
    setQuickLaunchMessage("System switched off. Metrics reset to zero.");
  };

  const handleRealtimeDrilldown = (event: unknown) => {
    const payload = extractChartPayload<MonitoringPointWithCompare>(event);
    if (!payload) {
      return;
    }

    const primaryValue = metricValue(payload, activeChart, false);
    const compareValue = metricValue(payload, activeChart, true);
    const hasCompare = compareMode && Number.isFinite(compareValue);
    const interventionTimeline =
      runTelemetry?.decoder_interventions
        .slice(-4)
        .map(
          (row) =>
            `Round ${row.round + 1}: ${row.decoder} flips=${row.flips}, residual=${row.residual_weight}`,
        ) ?? [];

    setDrilldown({
      source: "realtime",
      title: `${chartLabel(activeChart)} @ ${payload.slot}`,
      summary: `${decoderLabel(activeDecoder)} ${
        activeChart === "latency" ? `${primaryValue.toFixed(1)} ms` : `${primaryValue.toFixed(2)}`
      }`,
      keyValues: [
        { label: "Provider", value: drilldownProviderName },
        { label: "Run", value: activeRunId ?? "N/A" },
        { label: "Decoder", value: decoderLabel(activeDecoder) },
        {
          label: "Primary value",
          value:
            activeChart === "latency"
              ? `${primaryValue.toFixed(1)} ms`
              : activeChart === "noise"
                ? `${(primaryValue * 100).toFixed(2)}%`
                : `${primaryValue.toFixed(2)}%`,
        },
        {
          label: "Compare value",
          value: hasCompare
            ? activeChart === "latency"
              ? `${compareValue.toFixed(1)} ms`
              : activeChart === "noise"
                ? `${(compareValue * 100).toFixed(2)}%`
                : `${compareValue.toFixed(2)}%`
            : "N/A",
        },
      ],
      timeline:
        interventionTimeline.length > 0
          ? interventionTimeline
          : activityFeed.slice(0, 4).map((item) => `${item.time}: ${item.text}`),
    });
  };

  const handlePhysicalDrilldown = (event: unknown) => {
    const payload = extractChartPayload<PhysicalNoisePoint>(event);
    if (!payload) {
      return;
    }
    const roundInterventions =
      runTelemetry?.decoder_interventions
        .filter((row) => row.round === payload.round - 1)
        .map(
          (row) =>
            `${decoderLabel(parseDecoderKey(row.decoder) ?? activeDecoder)} flips=${row.flips}, residual=${
              row.residual_weight
            }`,
        ) ?? [];

    setDrilldown({
      source: "physical",
      title: `Physical Channel Round ${payload.round}`,
      summary: `PER ${payload.physicalErrorPct.toFixed(3)}% | Photon Loss ${payload.photonLossPct.toFixed(3)}%`,
      keyValues: [
        { label: "Provider", value: drilldownProviderName },
        { label: "Run", value: activeRunId ?? "N/A" },
        { label: "Round", value: payload.round.toString() },
        { label: "Physical Error Rate", value: `${payload.physicalErrorPct.toFixed(3)}%` },
        { label: "Photon Loss Rate", value: `${payload.photonLossPct.toFixed(3)}%` },
        { label: "Displacement Sigma", value: payload.displacementSigma.toFixed(4) },
      ],
      timeline:
        roundInterventions.length > 0
          ? roundInterventions
          : ["No decoder interventions recorded for this round."],
    });
  };

  const renderInterpretationPanel = () => (
    <div className="qec-sidepanel ops-console">
      <div className="ops-console-head">
        <div className="panel-title">Realtime Decoder Console</div>
        <span className={`status-badge ${streamingStatusClass}`}>
          ● {streamingStatusLabel}
        </span>
      </div>
      <div className="panel-subtitle">Intervention load trend and live event tape.</div>

      <div className="ops-console-kpis">
        <div className="ops-console-kpi">
          <span>Decoder</span>
          <strong>{decoderLabel(activeDecoder)}</strong>
        </div>
        <div className="ops-console-kpi">
          <span>PER</span>
          <strong>{perValue !== null ? `${perValue.toFixed(3)}%` : "N/A"}</strong>
        </div>
        <div className="ops-console-kpi">
          <span>Session</span>
          <strong>
            {activeIntegrationSession
              ? `#${activeIntegrationSession.id.slice(0, 8).toUpperCase()} ${sessionStatusLabel(
                  activeIntegrationSession.status,
                )}`
              : "none"}
          </strong>
        </div>
      </div>

      <div className="ops-timeline">
        <div className="ops-timeline-head">
          <span>Intervention Load</span>
          <span>{latestInterventionRoundLabel}</span>
        </div>
        <div className="ops-intervention-meta">
          <span>Round Aggregate</span>
          <strong>
            {opsInterventionSeries.length > 0
              ? `${opsInterventionSeries[opsInterventionSeries.length - 1]?.loadIndex.toFixed(1)}% load`
              : "No load"}
          </strong>
        </div>
        <div className="ops-intervention-chart">
          <ResponsiveContainer width="100%" height={168}>
            <LineChart data={opsInterventionSeries} margin={{ top: 8, right: 10, left: 2, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(143,158,180,0.2)" />
              <XAxis dataKey="roundLabel" tick={{ fill: "#8f9eb4", fontSize: 10 }} tickMargin={8} />
              <YAxis yAxisId="work" width={36} tick={{ fill: "#8f9eb4", fontSize: 10 }} />
              <YAxis
                yAxisId="load"
                orientation="right"
                domain={[0, 100]}
                unit="%"
                width={36}
                tick={{ fill: "#8f9eb4", fontSize: 10 }}
              />
              <Tooltip
                formatter={(value, name) => {
                  const numeric = numericValue(value);
                  if (name === "Load Index") {
                    return [`${numeric.toFixed(1)}%`, name];
                  }
                  return [numeric.toFixed(1), name];
                }}
                contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                labelStyle={{ color: "#c8d0db" }}
              />
              <Line yAxisId="work" type="monotone" dataKey="totalFlips" name="Flips" stroke="#3f89ea" strokeWidth={2.1} dot={false} />
              <Line
                yAxisId="work"
                type="monotone"
                dataKey="totalResidual"
                name="Residual Weight"
                stroke="#f0982f"
                strokeWidth={2.1}
                dot={false}
              />
              <Line
                yAxisId="load"
                type="monotone"
                dataKey="loadIndex"
                name="Load Index"
                stroke="#e25564"
                strokeWidth={1.9}
                strokeDasharray="5 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="ops-log-head">
        <span>Live Event Stream</span>
        <span>{mode === "api" ? "Live API" : "Mock Feed"}</span>
      </div>
      <div className="ops-log-stream">
        {opsLiveEvents.map((event, index) => (
          <div key={event.id} className={`ops-log-item level-${event.level} ${index === 0 ? "is-current" : ""}`}>
            <span className="ops-log-led" />
            <span className="ops-log-msg">{event.text}</span>
            <span className="ops-log-meta">{event.tag}</span>
          </div>
        ))}
      </div>
    </div>
  );

  const rightRailHost = typeof document !== "undefined" ? document.getElementById("app-right-rail") : null;
  const circuitDesignProviderFamily: CircuitProviderFamily = pendingCircuitLaunch
    ? resolveProviderFamily(pendingCircuitLaunch.provider)
    : launchProvider
      ? resolveProviderFamily(launchProvider)
      : "unknown";
  const liveConsoleRail = (
    <div className="decoder-live-rail">
      <div className="workflow-section workflow-section-compact">
        <div className="section-title">Live Console</div>
        <div className="panel-subtitle">Realtime decoder stream for operator context.</div>
        <button
          className="btn btn-secondary scientific-console-toggle"
          onClick={() => setShowLiveConsole((current) => !current)}
        >
          {showLiveConsole ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
          <span>{showLiveConsole ? "Hide Live Console" : "Show Live Console"}</span>
        </button>
        {showLiveConsole ? (
          renderInterpretationPanel()
        ) : (
          <div className="scientific-muted-note">Live console hidden.</div>
        )}
      </div>
      <div className="workflow-section workflow-section-compact decoder-rail-status">
        <div className="section-title">Scientific Summary</div>
        <div className="panel-subtitle">
          Logical correction view with hardware-derived evidence and exact denominators.
          <span className={`status-badge ${scientificExactnessClass} scientific-badge-inline`}>● {scientificExactnessLabel}</span>
          {sessionRunning && scientificState.state === "INGESTING" ? (
            <span className="status-badge status-running scientific-badge-inline">
              ● Session running — ingesting telemetry
            </span>
          ) : null}
        </div>
        <ScientificStateBanner result={scientificState} />
        {scientificState.state === "VALIDATED" ? (
          <div className="scientific-muted-note">
            <strong>Scientific validation passed.</strong> Exact scientific contracts and validation checks are both
            satisfied.
          </div>
        ) : null}
        {scientificState.state === "DEGRADED" ? <ScientificIntegrityAlert issues={scientificState.integrityIssues} /> : null}
        {scientificState.state === "IDLE" ? (
          <ScientificEmptyState
            onStartScientificSession={handleStartScientificSession}
            onOpenSessionLauncher={() => setSessionLauncherMenuOpen(true)}
            startDisabled={Boolean(scientificSessionUnavailableReason) || launcherStatus === "launching"}
            startDisabledReason={scientificSessionUnavailableReason}
            launcherDisabled={launcherStatus === "launching"}
          />
        ) : null}
        {scientificState.state === "INGESTING" ? (
          <div className="scientific-ingesting-list">
            {scientificIngestingRows.map((row) => (
              <div key={row.label} className="scientific-ingesting-item">
                <span>{row.label}</span>
                <strong>{row.value}</strong>
              </div>
            ))}
            {scientificIngestingRows.length === 0 ? (
              <div className="scientific-ingesting-item">
                <span>Status</span>
                <strong>Computing logical metrics...</strong>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <>
      <div className="dashboard-top-stack">
        <div className="header dashboard-header">
          <div>
            <h1>LiDMaS+ Decoder</h1>
            <p>Scientific decoder instrument for logical correction</p>
          </div>
          <div className={healthBadgeClass}>● {healthBadgeLabel}</div>
        </div>

        <div className="trust-strip">
          <div className="trust-item">
            <span>Hardware / Provider</span>
            <strong>{heroHardwareLabel} · {heroProviderLabel}</strong>
          </div>
          <div className="trust-item">
            <span>Run / Session</span>
            <strong>Run {activeRunShortId} · Session {activeSessionShortId}</strong>
          </div>
          <div className="trust-item">
            <span>Mode</span>
            <strong>Scientific</strong>
          </div>
          <div className="trust-item">
            <span>Active Decoder</span>
            <strong>{decoderLabel(activeDecoder)}</strong>
          </div>
          <div className="trust-item">
            <span>Data Source / Exactness</span>
            <strong>
              {systemOff ? "Off" : !systemArmed ? "Standby" : mode === "api" ? "Live API" : "GKP Mock"} · {scientificExactnessLabel}
            </strong>
          </div>
          <div className="trust-item">
            <span>Last Refresh</span>
            <strong>{systemOff ? "off" : !systemArmed ? "standby" : formatAgo(dataUpdatedAt)}</strong>
          </div>
          <div className="trust-item">
            <span>Exactness Notes</span>
            <strong>{scientificMissingSignalsLabel}</strong>
          </div>
        </div>

        <div className="dashboard-filterbar decoder-top-controls">
          <div className="filter-group">
            <label>Time Range</label>
            <select
              className="select-field research-select"
              value={timeRangeFilter}
              onChange={(event) => setFilterParam("range", event.target.value, "1h")}
            >
              <option value="1h">Last 1h</option>
              <option value="6h">Last 6h</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7d</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Provider</label>
            <select
              className="select-field research-select"
              value={providerFilter}
              onChange={(event) => setFilterParam("provider", event.target.value, "all")}
            >
              <option value="all">All Providers</option>
              {groupedProviderOptions.hardware.length > 0 ? (
                <optgroup label="Hardware Data">
                  {groupedProviderOptions.hardware.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {groupedProviderOptions.simulators.length > 0 ? (
                <optgroup label="Simulators">
                  {groupedProviderOptions.simulators.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </optgroup>
              ) : null}
            </select>
          </div>
          <div className="filter-group">
            <label>Neural Model</label>
            <input
              type="text"
              className="search-box research-search"
              value={neuralModelPath}
              onChange={(event) => setNeuralModelPath(event.target.value)}
              placeholder="/absolute/path/to/model.onnx"
            />
          </div>
          <div className="filter-group decoder-top-actions">
            <label>Actions</label>
            <div className="decoder-inline-actions">
              <SessionLauncherButton
                launchStatus={launcherStatus}
                isMenuOpen={sessionLauncherMenuOpen}
                providerOptions={launcherProviderOptions}
                selectedProviderId={launcherProviderId}
                onSelectProvider={setLauncherProviderId}
                onToggleMenu={() => setSessionLauncherMenuOpen((current) => !current)}
                onStartScientific={handleStartScientificSession}
                onOpenBenchmark={handleOpenBenchmarkDialog}
                onOpenReplay={handleOpenReplayDialog}
                onStopSession={handleStopSession}
                onViewRun={handleViewRun}
                canViewRun={Boolean(activeRunId)}
                scientificDisabledReason={scientificSessionUnavailableReason}
                benchmarkDisabledReason={benchmarkMenuDisabledReason}
                replayDisabledReason={replaySessionUnavailableReason}
                showIngestingChip={sessionRunning && scientificState.state === "INGESTING"}
              />
              <button className="btn btn-secondary decoder-inline-btn" onClick={() => navigate("/decoder/telemetry")}>
                <Activity size={13} aria-hidden="true" />
                <span>Telemetry</span>
              </button>
              <button className="btn btn-secondary decoder-inline-btn" onClick={() => navigate("/decoder/validation")}>
                <ShieldCheck size={13} aria-hidden="true" />
                <span>Validation</span>
              </button>
              <button className="btn btn-secondary decoder-inline-btn" onClick={() => navigate("/decoder/logs")}>
                <Activity size={13} aria-hidden="true" />
                <span>Logs</span>
              </button>
              <button className={`decoder-inline-btn btn ${systemOff ? "btn-status-warning" : "btn-status-failed"}`} onClick={handleSystemOff}>
                <Power size={13} aria-hidden="true" />
                <span>{systemOff ? "On" : "Off"}</span>
              </button>
            </div>
          </div>
        </div>

        <div className="decoder-buttons">
          {DECODERS.map((decoder) => (
            <button
              key={`top-run-decoder-${decoder.key}`}
              className={`decoder-btn ${activeDecoder === decoder.key ? "active" : ""}`}
              onClick={() => setActiveDecoder(decoder.key)}
            >
              {decoder.label}
            </button>
          ))}
        </div>

        <div className="scope-meta">
          Scope: {providerCount} providers, {jobsCount} jobs, {runsCount} runs. Active provider: {activeProviderName}.
          {" "}Launch provider state: {providerOperationalStateText}.
          {showingHistoricalEvidenceRun ? (
            <span className="decoder-action-feedback decoder-action-feedback-info">
              {" "}
              Showing latest run with scientific evidence (Run{" "}
              {latestScopedRunWithEvidence?.id.slice(0, 8).toUpperCase()}) while the newest run has no telemetry yet.
            </span>
          ) : null}
          {usingWarmupTelemetry ? (
            <span className="decoder-action-feedback decoder-action-feedback-info">
              {" "}
              Session is warming up. Showing provisional telemetry until the first exact replay frames arrive.
            </span>
          ) : null}
          {activeDecoder === "neural_mwpm" ? (
            <span
              className={`decoder-action-feedback ${
                neuralModelPath.trim() ? "decoder-action-feedback-info" : "decoder-action-feedback-error"
              }`}
            >
              {" "}
              {neuralModelPath.trim()
                ? "Neural model path configured."
                : "Set Neural Model path before running neural_mwpm in replay mode."}
            </span>
          ) : null}
          {quickLaunchMessage ? (
            <span className={`decoder-action-feedback decoder-action-feedback-${quickLaunchTone}`}>
              {" "}
              {quickLaunchMessage}
            </span>
          ) : null}
        </div>
        {activeRunId ? (
          <div className="session-link-cta">
            <button className="btn btn-secondary btn-small" onClick={handleViewRun}>
              View Run
            </button>
            <button className="btn btn-secondary btn-small" onClick={handleOpenTelemetryForRun}>
              Open Telemetry
            </button>
            <button className="btn btn-secondary btn-small" onClick={handleOpenValidationForRun}>
              Open Validation
            </button>
            <button className="btn btn-secondary btn-small" onClick={() => navigate("/decoder/logs")}>
              Open Logs
            </button>
          </div>
        ) : null}
      </div>

      <section className="research-summary-surface">
        <div className="section-title">Scientific Summary</div>
        <div className="panel-subtitle">Exact scientific decoder metrics for the selected run and decoder.</div>
        <div className="scientific-metrics-layout">
          <div className="kpi-grid scientific-primary-grid">
            {scientificPrimaryCards.map(({ key, contract }) => (
              <ScientificMetricCard
                key={key}
                contract={contract}
                result={scientificState}
                value={scientificCardValues[key]}
                forceVisible={scientificZeroBaseline}
                zeroBaseline={scientificZeroBaseline}
              />
            ))}
          </div>

          <div className="table-container scientific-detail-container">
            <div className="table-wrapper">
              <div className="section-title">Scientific Detail</div>
              <div className="panel-subtitle">Secondary exact counts and state-aware availability reasons.</div>
              <div className="scientific-detail-list">
                {scientificSecondaryCards.map(({ key, contract, availability }) => (
                  <div
                    key={key}
                    className={`scientific-detail-row ${availability.available || scientificZeroBaseline ? "" : "is-unavailable"}`}
                  >
                    <span>{contract.label}</span>
                    <strong>
                      {availability.available || scientificZeroBaseline
                        ? scientificCardValues[key]
                        : `${contract.label} unavailable — ${availability.availabilityReason}`}
                    </strong>
                  </div>
                ))}
                <div className="scientific-detail-row">
                  <span>Decoder policy readout</span>
                  <strong>{decoderLabel(activeDecoder)} selected in scientific mode</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

        {scientificZeroBaseline ? (
          <div className="scientific-muted-note">
            Scientific summary initialized. Values remain zero until a job/run starts and telemetry is ingested.
          </div>
        ) : null}

        {scientificState.state === "PARTIAL" && scientificMissingPrimaryReasons.length > 0 ? (
          <div className="scientific-muted-note">
            {scientificMissingPrimaryReasons.map((reason) => (
              <div key={reason}>{reason}</div>
            ))}
          </div>
        ) : null}

        <div className="section-title">Operational Diagnostics</div>
        <div className="panel-subtitle">Runtime and synthetic indicators separated from scientific metrics.</div>
        <div className="kpi-grid">
          {operationalKpiCards.map((card) => {
            const trendPositive = card.trendUpGood ? card.trendDelta >= 0 : card.trendDelta <= 0;
            return (
              <div key={card.key} className="kpi-card">
                <div className="kpi-label">{card.label}</div>
                <div className="kpi-value">{card.value}</div>
                <div className={`kpi-trend ${trendPositive ? "good" : "bad"}`}>{card.trendText}</div>
              </div>
            );
          })}
        </div>

        <div className="panels">
          <section className="panel panel-blue">
            <div className="panel-title">Platform Health</div>
            <div className="panel-subtitle">Backend status</div>
            <div className="panel-row">
              <span className="panel-row-label">Status</span>
              <span className="panel-row-value">
                {systemOff
                  ? "Off"
                  : isApi && healthQuery.isError
                  ? "API unreachable"
                  : isApi && healthQuery.isLoading
                    ? "Loading"
                    : healthData?.status ?? "Unavailable"}
              </span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Uptime</span>
              <span className="panel-row-value">
                {systemOff ? "0s" : healthData ? `${uptimeSeconds.toLocaleString()}s` : "—"}
              </span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Latency</span>
              <span className="panel-row-value">
                {systemOff
                  ? "0ms"
                  : healthProbeLatencyMs !== null
                  ? `${healthProbeLatencyMs}ms`
                  : isApi && healthQuery.isLoading
                    ? "Probing..."
                    : "—"}
              </span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Version</span>
              <span className="panel-row-value">
                {systemOff ? "—" : healthData?.version ?? (isApi ? "—" : "v0.1.0")}
              </span>
            </div>
          </section>

          <section className="panel panel-green">
            <div className="panel-title">Workspace</div>
            <div className="panel-subtitle">Active entities</div>
            <div className="panel-row">
              <span className="panel-row-label">Providers</span>
              <span className="panel-row-value">{providerCount} / 12</span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Jobs Queue</span>
              <span className="panel-row-value">{queuedJobsCount}</span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Runs Active</span>
              <span className="panel-row-value">{activeRunsCount}</span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Scope Payload</span>
              <span className="panel-row-value">{formatBytes(scopePayloadBytes)}</span>
            </div>
            <div className="panel-row">
              <span className="panel-row-label">Hardware Mix</span>
              <span className="panel-row-value">{hardwareMix.length > 0 ? hardwareMix[0].label : "Unknown"}</span>
            </div>
          </section>

          <section className="panel panel-orange">
            <div className="panel-title-row">
              <div>
                <div className="panel-title">Activity Feed</div>
                <div className="panel-subtitle">Recent events and runtime mode</div>
              </div>
              <span className="status-badge status-running">
                ● {mode === "api" ? "Live API" : "GKP Mock"}
              </span>
            </div>

            {activityFeed.map((item, index) => (
              <div key={`${item.text}-${index}`} className="activity-item">
                <span className={`activity-dot ${item.tone}`} />
                <span className="activity-text">{item.text}</span>
                <span className="activity-time">{item.time}</span>
              </div>
            ))}
          </section>
        </div>
      </section>

      <div className="qec-map-section">
        <div className="section-title">QEC Encoding State Map</div>
        <div className="qec-map-selector" role="tablist" aria-label="Encoding map selector">
          <button
            className={`qec-map-select-btn ${encodingMapMode === "surface" ? "active" : ""}`}
            onClick={() => setEncodingMapMode("surface")}
            role="tab"
            aria-selected={encodingMapMode === "surface"}
          >
            Surface Syndrome (Outer)
          </button>
          <button
            className={`qec-map-select-btn ${encodingMapMode === "gkp" ? "active" : ""}`}
            onClick={() => setEncodingMapMode("gkp")}
            role="tab"
            aria-selected={encodingMapMode === "gkp"}
          >
            Raw GKP Oscillator (Inner)
          </button>
        </div>
        {encodingMapMode === "surface" ? (
          <div className="qec-distance-controls" role="group" aria-label="Outer code distance selector">
            <span className="qec-distance-label">Outer code</span>
            <div className="qec-distance-selector">
              {[3, 5, 7].map((distance) => (
                <button
                  key={`outer-distance-${distance}`}
                  className={`qec-distance-btn ${outerCodeDistance === distance ? "active" : ""}`}
                  onClick={() => setFilterParam("outerDistance", String(distance), "3")}
                  title={`Set outer code distance to d=${distance}`}
                >
                  d={distance}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <div className="qec-map-layout">
          <section className="qec-map-panel">
            <div className="qec-map-head">
              <div>
                <div className="monitoring-chart-title">{qecMapHeading}</div>
                <div className="panel-subtitle">{qecMapSubtitle}</div>
              </div>
              <span className={`status-badge ${streamingStatusClass}`}>
                ● {extractionStatusLabel}
              </span>
            </div>

            {encodingMapMode === "surface" && latestRoundSyndromes.length > 0 ? (
              <div className="qec-map-board">
                <svg
                  className="qec-map-svg"
                  viewBox="0 0 620 340"
                  role="img"
                  aria-label="QEC lattice map with active syndrome indicators"
                >
                  {qecLattice.edges.map((edge) => (
                    <line
                      key={edge.key}
                      className="qec-map-edge"
                      x1={edge.x1}
                      y1={edge.y1}
                      x2={edge.x2}
                      y2={edge.y2}
                    />
                  ))}
                  {qecPointerNodes.map((node) => {
                    const bubbleX = Math.min(548, node.x + 16);
                    const bubbleY = Math.max(16, node.y - 22);
                    return (
                      <g
                        key={`pointer-${node.key}`}
                        className={`qec-map-pointer ${syndromeExtractionActive ? "is-live" : ""}`}
                      >
                        <line x1={node.x + 7} y1={node.y - 7} x2={bubbleX} y2={bubbleY + 6} />
                        <rect x={bubbleX - 2} y={bubbleY - 4} rx={4} ry={4} width={44} height={16} />
                        <text x={bubbleX + 20} y={bubbleY + 8} textAnchor="middle">
                          {node.label}
                        </text>
                      </g>
                    );
                  })}
                  {qecLattice.nodes.map((node) => (
                    <g key={`node-${node.key}`} transform={`translate(${node.x}, ${node.y})`}>
                      <circle
                        className={`qec-map-node-core ${node.triggered ? "is-triggered" : "is-stable"} ${
                          node.triggered && syndromeExtractionActive ? "is-blinking" : ""
                        }`}
                        r={10}
                      />
                      <circle
                        className={`qec-map-node-ring ${node.triggered ? "is-triggered" : "is-stable"} ${
                          node.triggered && syndromeExtractionActive ? "is-blinking" : ""
                        }`}
                        r={16}
                      />
                      <text className="qec-map-node-label" y={27} textAnchor="middle">
                        {node.label}
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
            ) : null}

            {encodingMapMode === "surface" && latestRoundSyndromes.length === 0 ? (
              <div className="empty-card">
                {telemetryInitializing
                  ? "Scientific session started. Waiting for first syndrome telemetry batch from replay."
                  : "No syndrome extraction stream found for the active run. Start a run with telemetry to render the lattice map."}
              </div>
            ) : null}

            {encodingMapMode === "gkp" && gkpOscillatorMapPoints.length > 0 ? (
              <div className="qec-map-board">
                <svg className="qec-map-svg" viewBox="0 0 620 340" role="img" aria-label="GKP oscillator phase map">
                  <line className="gkp-map-axis" x1={74} y1={170} x2={546} y2={170} />
                  <line className="gkp-map-axis" x1={310} y1={44} x2={310} y2={296} />
                  <rect className="gkp-map-boundary" x={74} y={44} width={472} height={252} rx={10} ry={10} />
                  <text className="gkp-map-axis-label" x={548} y={164}>
                    +q
                  </text>
                  <text className="gkp-map-axis-label" x={314} y={52}>
                    +p
                  </text>
                  <text className="gkp-map-axis-label" x={84} y={188}>
                    -q
                  </text>
                  <text className="gkp-map-axis-label" x={314} y={292}>
                    -p
                  </text>

                  {gkpPointerPoints.map((point) => {
                    const bubbleX = Math.min(542, point.x + 14);
                    const bubbleY = Math.max(18, point.y - 18);
                    return (
                      <g key={`gkp-pointer-${point.key}`} className="gkp-map-pointer">
                        <line x1={point.x + 6} y1={point.y - 6} x2={bubbleX} y2={bubbleY + 4} />
                        <rect x={bubbleX - 2} y={bubbleY - 4} rx={4} ry={4} width={56} height={16} />
                        <text x={bubbleX + 26} y={bubbleY + 8} textAnchor="middle">
                          {point.mode}
                        </text>
                      </g>
                    );
                  })}

                  {gkpOscillatorMapPoints.map((point) => (
                    <g key={point.key} transform={`translate(${point.x}, ${point.y})`}>
                      <circle
                        className={`gkp-map-point ${point.flagged ? "is-flagged" : "is-stable"} ${
                          point.flagged && syndromeExtractionActive ? "is-blinking" : ""
                        }`}
                        r={point.flagged ? 4.8 : 3.6}
                      />
                    </g>
                  ))}
                </svg>
              </div>
            ) : null}

            {encodingMapMode === "gkp" && gkpOscillatorMapPoints.length === 0 ? (
              <div className="empty-card">
                No raw GKP oscillator state telemetry was found. Add `gkp_oscillator_states` in run telemetry to
                visualize direct phase-space states.
              </div>
            ) : null}
          </section>

          <aside className="qec-map-metrics">
            {encodingMapMode === "surface" ? (
              <>
                <div className="qec-map-metric-card">
                  <span>Stabilizers Tracked</span>
                  <strong>
                    {qecTrackedTotal} / {qecStabilizerTotal}
                  </strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Triggered This Round</span>
                  <strong>{qecTriggeredNodes.length}</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Triggered Density</span>
                  <strong>{qecTriggeredPct.toFixed(1)}%</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Extraction State</span>
                  <strong>{systemOff ? "Off" : syndromeExtractionActive ? "Running" : "Idle"}</strong>
                </div>
                <div className="qec-map-alerts">
                  <div className="qec-map-alerts-title">Active Syndrome Pointers</div>
                  {qecTriggeredNodes.length === 0 ? (
                    <div className="qec-map-alert-empty">No triggered syndrome checks in the latest round.</div>
                  ) : (
                    qecTriggeredNodes.slice(0, 12).map((node) => (
                      <div key={`alert-${node.key}`} className="qec-map-alert-item">
                        <span className="qec-map-alert-key">{node.label}</span>
                        <span className="qec-map-alert-value">value {node.value}</span>
                      </div>
                    ))
                  )}
                </div>
                {qecMapTrimmed ? (
                  <div className="qec-map-trim-note">Map view capped to first 64 stabilizers for readability.</div>
                ) : null}
              </>
            ) : (
              <>
                <div className="qec-map-metric-card">
                  <span>Oscillator Modes</span>
                  <strong>{gkpModesTracked}</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Flagged States</span>
                  <strong>{gkpFlaggedPoints.length}</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Mean Variance</span>
                  <strong>{gkpVarianceAvg.toFixed(4)}</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Mean Energy</span>
                  <strong>{gkpEnergyAvg.toFixed(4)}</strong>
                </div>
                <div className="qec-map-metric-card">
                  <span>Phase Range</span>
                  <strong>±{gkpAxisLimit.toFixed(1)}</strong>
                </div>
                <div className="qec-map-alerts">
                  <div className="qec-map-alerts-title">Flagged Oscillator States</div>
                  {gkpFlaggedPoints.length === 0 ? (
                    <div className="qec-map-alert-empty">No flagged oscillator states in current telemetry.</div>
                  ) : (
                    gkpFlaggedPoints.slice(0, 12).map((point) => (
                      <div key={`gkp-alert-${point.key}`} className="qec-map-alert-item">
                        <span className="qec-map-alert-key">{point.mode}</span>
                        <span className="qec-map-alert-value">
                          q {point.q.toFixed(3)}, p {point.p.toFixed(3)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
                {gkpOscillatorFallback ? (
                  <div className="qec-map-trim-note">
                    Raw oscillator stream unavailable: displaying projection derived from physical telemetry.
                  </div>
                ) : null}
              </>
            )}
          </aside>
        </div>
      </div>

      <div className="monitoring-section">
        <div className="section-title">Physical Noise & Realtime Monitor</div>
        <div className={`monitoring-layout ${isPhysicalPanelCollapsed ? "collapsed" : ""}`}>
          <section className={`monitoring-left-panel ${isPhysicalPanelCollapsed ? "collapsed" : ""}`}>
            <div className="monitoring-panel-head">
              <div className="monitoring-chart-title">Physical Channel Noise (Pre-QEC)</div>
              <button
                className="panel-collapse-btn"
                onClick={() => setPhysicalPanelCollapsed((current) => !current)}
              >
                {isPhysicalPanelCollapsed ? "Expand" : "Collapse"}
              </button>
            </div>

            {isPhysicalPanelCollapsed ? (
              <div className="panel-collapsed-content">
                <span>PER</span>
                <strong>{perValue !== null ? `${perValue.toFixed(3)}%` : "N/A"}</strong>
              </div>
            ) : (
              <>
                {physicalNoiseLoading ? (
                  <div className="empty-card">Loading physical noise telemetry from backend...</div>
                ) : null}
                {telemetryUnavailableForRun || telemetryInitializing ? (
                  <div className="empty-card">
                    {telemetryInitializing
                      ? "Scientific session started. Waiting for first physical-noise batch from replay."
                      : "No physical telemetry has been ingested for this run yet. Start or resume a scientific session to stream pre-QEC physical noise."}
                  </div>
                ) : null}
                {physicalNoiseError ? (
                  <div className="empty-card">Failed to load physical noise telemetry from backend.</div>
                ) : null}
                {!physicalNoiseLoading && !physicalNoiseError && physicalNoiseData.length > 0 ? (
                  <div className="visualization-area">
                    <div className="physical-chart-meta">
                      <span>Latest sample: QEC round {latestPhysicalPoint ? latestPhysicalPoint.round : "N/A"}</span>
                      <span
                        className={`physical-chart-threshold ${
                          perValue !== null && perValue >= anomalyThresholds.perWarn ? "is-breach" : "is-ok"
                        }`}
                      >
                        PER warning threshold {anomalyThresholds.perWarn.toFixed(1)}%
                      </span>
                    </div>
                    <div className="physical-chart-legend" role="list" aria-label="Physical channel signals">
                      {PHYSICAL_LEGEND_SIGNALS.map((signal) => (
                        <span key={signal.id} className="physical-chart-legend-item" role="listitem">
                          <span className="physical-chart-legend-icon" style={{ backgroundColor: signal.color }}>
                            <span className="physical-chart-legend-dot" style={{ borderColor: signal.color }} />
                          </span>
                          <span>{signal.label}</span>
                          <strong className="physical-chart-legend-value">{signal.format(latestPhysicalPoint)}</strong>
                        </span>
                      ))}
                    </div>
                    <ResponsiveContainer width="100%" height={360}>
                      <LineChart
                        data={physicalNoiseData}
                        margin={{ top: 12, right: 20, left: 12, bottom: 18 }}
                        onClick={handlePhysicalDrilldown}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                        <XAxis
                          dataKey="round"
                          tick={{ fill: "#8f9eb4", fontSize: 10 }}
                          label={{ value: "QEC Round", position: "insideBottom", offset: -6, fill: "#8f9eb4", fontSize: 10 }}
                        />
                        <YAxis
                          yAxisId="pct"
                          domain={[0, physicalPctCeiling]}
                          width={44}
                          tickCount={6}
                          tick={{ fill: "#8f9eb4", fontSize: 10 }}
                          unit="%"
                          label={{ value: "Error / Loss (%)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 10 }}
                        />
                        <YAxis
                          yAxisId="sigma"
                          domain={[0, physicalSigmaCeiling]}
                          orientation="right"
                          width={44}
                          tickCount={6}
                          tick={{ fill: "#8f9eb4", fontSize: 10 }}
                          label={{ value: "Sigma", angle: 90, position: "insideRight", fill: "#8f9eb4", fontSize: 10 }}
                        />
                        <Tooltip
                          formatter={(value, name) => {
                            const numeric = numericValue(value);
                            if (name === "Displacement Sigma") {
                              return [numeric.toFixed(4), "Displacement Sigma"];
                            }
                            return [`${numeric.toFixed(3)}%`, name];
                          }}
                          contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                          labelStyle={{ color: "#c8d0db" }}
                        />
                        <ReferenceArea
                          yAxisId="pct"
                          y1={anomalyThresholds.perWarn}
                          y2={physicalPctCeiling}
                          fill="rgba(226,85,100,0.12)"
                        />
                        <ReferenceLine
                          yAxisId="pct"
                          y={anomalyThresholds.perWarn}
                          stroke="#e25564"
                          strokeDasharray="4 4"
                          strokeOpacity={0.7}
                        />
                        <Line
                          yAxisId="pct"
                          type="monotone"
                          dataKey="physicalErrorPct"
                          name="Physical Error Rate (%)"
                          stroke="#e25564"
                          strokeWidth={2.2}
                          dot={false}
                        />
                        <Line
                          yAxisId="pct"
                          type="monotone"
                          dataKey="photonLossPct"
                          name="Photon Loss Rate (%)"
                          stroke="#f0982f"
                          strokeWidth={2.2}
                          dot={false}
                        />
                        <Line
                          yAxisId="sigma"
                          type="monotone"
                          dataKey="displacementSigma"
                          name="Displacement Sigma"
                          stroke="#3f89ea"
                          strokeWidth={2.2}
                          dot={false}
                        />
                        {physicalAnomalies.slice(0, 14).map((point) => (
                          <ReferenceDot
                            key={`physical-anomaly-${point.round}`}
                            yAxisId="pct"
                            x={point.round}
                            y={point.physicalErrorPct}
                            r={3}
                            fill="#e25564"
                            stroke="none"
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
                {!physicalNoiseLoading &&
                !physicalNoiseError &&
                !telemetryUnavailableForRun &&
                !telemetryInitializing &&
                physicalNoiseData.length === 0 ? (
                  <div className="empty-card">
                    Physical noise is captured before QEC and can be visualized directly when telemetry exists.
                  </div>
                ) : null}
              </>
            )}
          </section>

          <section className="monitoring-right-panel">
            <div className="monitoring-right-head">
              <div className="monitoring-chart-title">Real-Time Decoder Monitor</div>
              <div className="monitor-compare-controls">
                <div className="filter-group">
                  <label>Compare Mode</label>
                  <button
                    className={`btn btn-secondary monitor-compare-toggle ${compareMode ? "active" : ""}`}
                    onClick={() => setFilterParam("compare", compareMode ? "0" : "1", "0")}
                  >
                    {compareMode ? "Enabled" : "Disabled"}
                  </button>
                </div>
                <div className="filter-group">
                  <label>Compare Decoder</label>
                  <select
                    className="select-field research-select"
                    value={compareDecoder}
                    onChange={(event) => setFilterParam("compareDecoder", event.target.value, fallbackCompareDecoder)}
                    disabled={!compareMode}
                  >
                    {DECODERS.filter((decoder) => decoder.key !== activeDecoder).map((decoder) => (
                      <option key={decoder.key} value={decoder.key}>
                        {decoder.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="decoder-buttons">
              {DECODERS.map((decoder) => (
                <button
                  key={decoder.key}
                  className={`decoder-btn ${activeDecoder === decoder.key ? "active" : ""}`}
                  onClick={() => setActiveDecoder(decoder.key)}
                >
                  {decoder.label}
                </button>
              ))}
            </div>

            <div className="metric-buttons">
              <button className={`metric-btn ${activeChart === "noise" ? "active" : ""}`} onClick={() => setActiveChart("noise")}>
                Noise Level
              </button>
              <button className={`metric-btn ${activeChart === "success" ? "active" : ""}`} onClick={() => setActiveChart("success")}>
                Success Rate
              </button>
              <button className={`metric-btn ${activeChart === "error" ? "active" : ""}`} onClick={() => setActiveChart("error")}>
                Error Rate
              </button>
              <button className={`metric-btn ${activeChart === "latency" ? "active" : ""}`} onClick={() => setActiveChart("latency")}>
                Latency Trend
              </button>
            </div>

            <div className="monitoring-chart-title">
              {chartLabel(activeChart)} · {decoderLabel(activeDecoder)}
            </div>
            {activeDecoderMissingTelemetry ? (
              <div className="monitor-warning-note">Selected decoder has no intervention stream in this run.</div>
            ) : null}
            {compareDecoderMissingTelemetry ? (
              <div className="monitor-warning-note">Compare decoder has no intervention stream in this run.</div>
            ) : null}
            {telemetryUnavailableForRun || telemetryInitializing ? (
              <div className="monitor-warning-note">
                {telemetryInitializing
                  ? `Session ${activeSessionShortId} is running. Waiting for first replay telemetry batch for run ${activeRunShortId}.`
                  : `No scientific telemetry is attached to run ${activeRunShortId} yet. Start a session or choose a run with telemetry.`}
              </div>
            ) : null}
            {runTelemetryHardError ? (
              <div className="monitor-warning-note">Failed to load realtime monitor telemetry from backend.</div>
            ) : null}
            {compareMode ? (
              <div className={`compare-delta ${compareIsGood ? "good" : "bad"}`}>
                Compare vs {decoderLabel(compareDecoder)}: {formatTrend(compareDelta)}
              </div>
            ) : null}
            <div className="visualization-area">
              {activeChart === "noise" && monitoringHasRows ? (
                <ResponsiveContainer width="100%" height={360}>
                  <AreaChart
                    data={monitoringData}
                    margin={{ top: 8, right: 16, left: 8, bottom: 18 }}
                    onClick={handleRealtimeDrilldown}
                  >
                    <defs>
                      <linearGradient id="dashboardNoise" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3f89ea" stopOpacity={0.36} />
                        <stop offset="100%" stopColor="#3f89ea" stopOpacity={0.04} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="slot"
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      tickMargin={8}
                      label={{ value: "Time Window", position: "insideBottom", offset: -6, fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <YAxis
                      width={52}
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      tickFormatter={(value: number) => `${(value * 100).toFixed(1)}%`}
                      label={{ value: "Noise Rate (%)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(value) => [`${(numericValue(value) * 100).toFixed(2)}%`, "Noise"]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <ReferenceArea
                      y1={anomalyThresholds.noiseWarn}
                      y2={anomalyThresholds.noiseCritical}
                      fill="rgba(240,152,47,0.12)"
                    />
                    <ReferenceArea y1={anomalyThresholds.noiseCritical} y2={0.05} fill="rgba(226,85,100,0.1)" />
                    <ReferenceLine
                      y={anomalyThresholds.noiseWarn}
                      stroke="#f0982f"
                      strokeDasharray="4 4"
                      strokeOpacity={0.8}
                    />
                    <Area type="monotone" dataKey="noise" stroke="#3f89ea" strokeWidth={2.4} fill="url(#dashboardNoise)" />
                    {compareMode ? (
                      <Line
                        type="monotone"
                        dataKey="compareNoise"
                        stroke="#8fd0ff"
                        strokeDasharray="5 4"
                        strokeWidth={2}
                        dot={false}
                      />
                    ) : null}
                    {noiseAnomalies.slice(0, 20).map((point) => (
                      <ReferenceDot
                        key={`noise-anomaly-${point.slot}`}
                        x={point.slot}
                        y={point.noise}
                        r={3}
                        fill="#f0982f"
                        stroke="none"
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              ) : null}

              {activeChart === "success" && monitoringHasRows ? (
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart
                    data={monitoringData}
                    margin={{ top: 8, right: 16, left: 8, bottom: 18 }}
                    onClick={handleRealtimeDrilldown}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="slot"
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      tickMargin={8}
                      label={{ value: "Time Window", position: "insideBottom", offset: -6, fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <YAxis
                      domain={[85, 100]}
                      width={52}
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      unit="%"
                      label={{ value: "Success Rate (%)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(value) => [`${numericValue(value).toFixed(2)}%`, "Success"]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <ReferenceArea y1={0} y2={anomalyThresholds.successWarn} fill="rgba(226,85,100,0.1)" />
                    <ReferenceLine
                      y={anomalyThresholds.successWarn}
                      stroke="#e25564"
                      strokeDasharray="4 4"
                      strokeOpacity={0.8}
                    />
                    <Line type="monotone" dataKey="success" stroke="#26b36b" strokeWidth={2.8} dot={false} />
                    {compareMode ? (
                      <Line
                        type="monotone"
                        dataKey="compareSuccess"
                        stroke="#8fd0ff"
                        strokeDasharray="5 4"
                        strokeWidth={2}
                        dot={false}
                      />
                    ) : null}
                    {successAnomalies.slice(0, 20).map((point) => (
                      <ReferenceDot
                        key={`success-anomaly-${point.slot}`}
                        x={point.slot}
                        y={point.success}
                        r={3}
                        fill="#e25564"
                        stroke="none"
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : null}

              {activeChart === "error" && monitoringHasRows ? (
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart
                    data={monitoringData}
                    margin={{ top: 8, right: 16, left: 8, bottom: 18 }}
                    onClick={handleRealtimeDrilldown}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="slot"
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      tickMargin={8}
                      label={{ value: "Time Window", position: "insideBottom", offset: -6, fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <YAxis
                      domain={[0, 15]}
                      width={52}
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      unit="%"
                      label={{ value: "Error Rate (%)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(value) => [`${numericValue(value).toFixed(2)}%`, "Error"]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <ReferenceArea y1={anomalyThresholds.errorWarn} y2={15} fill="rgba(226,85,100,0.12)" />
                    <ReferenceLine
                      y={anomalyThresholds.errorWarn}
                      stroke="#e25564"
                      strokeDasharray="4 4"
                      strokeOpacity={0.8}
                    />
                    <Line type="monotone" dataKey="error" stroke="#e25564" strokeWidth={2.8} dot={false} />
                    {compareMode ? (
                      <Line
                        type="monotone"
                        dataKey="compareError"
                        stroke="#8fd0ff"
                        strokeDasharray="5 4"
                        strokeWidth={2}
                        dot={false}
                      />
                    ) : null}
                    {errorAnomalies.slice(0, 20).map((point) => (
                      <ReferenceDot
                        key={`error-anomaly-${point.slot}`}
                        x={point.slot}
                        y={point.error}
                        r={3}
                        fill="#e25564"
                        stroke="none"
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : null}

              {activeChart === "latency" && monitoringHasRows ? (
                <ResponsiveContainer width="100%" height={360}>
                  <AreaChart
                    data={monitoringData}
                    margin={{ top: 8, right: 16, left: 8, bottom: 18 }}
                    onClick={handleRealtimeDrilldown}
                  >
                    <defs>
                      <linearGradient id="dashboardLatency" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f0982f" stopOpacity={0.34} />
                        <stop offset="100%" stopColor="#f0982f" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="slot"
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      tickMargin={8}
                      label={{ value: "Time Window", position: "insideBottom", offset: -6, fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <YAxis
                      width={52}
                      tick={{ fill: "#8f9eb4", fontSize: 10 }}
                      unit="ms"
                      label={{ value: "Latency (ms)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(value) => [`${numericValue(value).toFixed(1)} ms`, "Latency"]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <ReferenceArea y1={anomalyThresholds.latencyWarn} y2={180} fill="rgba(240,152,47,0.12)" />
                    <ReferenceLine
                      y={anomalyThresholds.latencyWarn}
                      stroke="#f0982f"
                      strokeDasharray="4 4"
                      strokeOpacity={0.8}
                    />
                    <Area type="monotone" dataKey="latency" stroke="#f0982f" strokeWidth={2.8} fill="url(#dashboardLatency)" />
                    {compareMode ? (
                      <Line
                        type="monotone"
                        dataKey="compareLatency"
                        stroke="#8fd0ff"
                        strokeDasharray="5 4"
                        strokeWidth={2}
                        dot={false}
                      />
                    ) : null}
                    {latencyAnomalies.slice(0, 20).map((point) => (
                      <ReferenceDot
                        key={`latency-anomaly-${point.slot}`}
                        x={point.slot}
                        y={point.latency}
                        r={3}
                        fill="#f0982f"
                        stroke="none"
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              ) : null}
              {!monitoringHasRows ? (
                <div className="empty-card">
                  {telemetryInitializing
                    ? "Realtime monitor is initializing from replay stream..."
                    : telemetryUnavailableForRun
                    ? `No realtime decoder telemetry is available for run ${activeRunShortId} yet.`
                    : runTelemetryHardError
                      ? "Realtime monitor data is temporarily unavailable due to a backend error."
                      : "Realtime monitor will populate when decoder telemetry is ingested."}
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </div>

      <div className="workflow-section">
        <div className="section-title">Operational Workflow</div>
        <div className="panel-subtitle">
          Non-scientific remediation workflow for operational anomalies.
        </div>
        <button
          className="btn btn-secondary scientific-console-toggle"
          onClick={() => setShowOperationalWorkflow((current) => !current)}
        >
          {showOperationalWorkflow ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
          <span>{showOperationalWorkflow ? "Hide Operational Workflow" : "Show Operational Workflow"}</span>
        </button>
        {showOperationalWorkflow ? (
          <div className="workflow-grid">
            {workflowAlerts.map((alert) => {
              const state = alertWorkflow[alert.id] ?? {
                acknowledged: false,
                owner: "Unassigned",
                notes: "",
              };
              return (
                <div key={alert.id} className={`workflow-card ${alert.level}`}>
                  <div className="workflow-head">
                    <div>
                      <div className="workflow-title">{alert.title}</div>
                      <div className="workflow-detail">{alert.detail}</div>
                    </div>
                    <span className={`status-badge status-${alert.level === "info" ? "running" : alert.level}`}>
                      {alert.level.toUpperCase()}
                    </span>
                  </div>
                  <div className="workflow-metric">{alert.metric}</div>
                  <div className="workflow-controls">
                    <button
                      className={`btn btn-secondary ${state.acknowledged ? "active" : ""}`}
                      onClick={() => updateWorkflowState(alert.id, { acknowledged: !state.acknowledged })}
                      disabled={!canEditWorkflow}
                    >
                      {state.acknowledged ? "Acknowledged" : "Acknowledge"}
                    </button>
                    <select
                      className="select-field research-select"
                      value={state.owner}
                      onChange={(event) => updateWorkflowState(alert.id, { owner: event.target.value })}
                      disabled={!canEditWorkflow}
                    >
                      <option value="Unassigned">Unassigned</option>
                      <option value="QEC Ops">QEC Ops</option>
                      <option value="Provider Team">Provider Team</option>
                      <option value="SRE">SRE</option>
                    </select>
                  </div>
                  <textarea
                    className="form-textarea workflow-notes"
                    placeholder="Resolution notes"
                    value={state.notes}
                    onChange={(event) => updateWorkflowState(alert.id, { notes: event.target.value })}
                    disabled={!canEditWorkflow}
                  />
                </div>
              );
            })}
          </div>
        ) : (
          <div className="scientific-muted-note">Operational workflow is collapsed in scientific mode.</div>
        )}
      </div>

      {rightRailHost ? createPortal(liveConsoleRail, rightRailHost) : null}

      <StartCircuitDesignDialog
        open={circuitDesignDialogOpen}
        pending={quickLaunchBusy}
        providerName={pendingCircuitLaunch?.provider.name ?? launchProvider?.name ?? "Provider"}
        providerFamily={circuitDesignProviderFamily}
        onClose={closeCircuitDesignDialog}
        onStart={handleStartSessionFromCircuitDesign}
      />
      <StartBenchmarkSessionDialog
        open={benchmarkDialogOpen}
        pending={quickLaunchBusy}
        decoderOptions={DECODERS}
        selectedDecoders={benchmarkDecoders}
        onToggleDecoder={handleToggleBenchmarkDecoder}
        onClose={() => setBenchmarkDialogOpen(false)}
        onStart={handleStartBenchmarkSession}
        disabledReason={benchmarkSessionUnavailableReason}
      />
      <StartReplaySessionDialog
        open={replayDialogOpen}
        pending={quickLaunchBusy}
        sources={replaySourceOptions}
        selectedSourceRunId={replaySourceRunId}
        onSelectSource={setReplaySourceRunId}
        onClose={() => setReplayDialogOpen(false)}
        onStart={handleStartReplaySession}
        disabledReason={replaySessionUnavailableReason}
      />
      <StartIbmApiKeyDialog
        open={ibmApiKeyDialogOpen}
        pending={setIbmApiKeyMutation.isPending}
        providerName={pendingIbmLaunch?.provider.name ?? "IBM"}
        apiKey={ibmApiKeyInput}
        ibmInstance={ibmInstanceInput}
        sourceMode={ibmLiveSourceMode}
        onApiKeyChange={(value) => {
          setIbmApiKeyInput(value);
          if (ibmApiKeyError) {
            setIbmApiKeyError(null);
          }
        }}
        onIbmInstanceChange={setIbmInstanceInput}
        onSourceModeChange={setIbmLiveSourceMode}
        onClose={closeIbmApiKeyDialog}
        onStart={handleConfirmIbmApiKeyAndLaunch}
        errorMessage={ibmApiKeyError}
      />

      {drilldown ? (
        <div className="drilldown-overlay" onClick={() => setDrilldown(null)}>
          <aside className="drilldown-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drilldown-header">
              <div>
                <div className="drilldown-title">{drilldown.title}</div>
                <div className="drilldown-summary">{drilldown.summary}</div>
              </div>
              <button className="btn-icon" onClick={() => setDrilldown(null)}>
                ×
              </button>
            </div>
            <div className="drilldown-meta">Source: {drilldown.source === "physical" ? "Physical Channel" : "Realtime Monitor"}</div>
            <div className="drilldown-kv">
              {drilldown.keyValues.map((entry) => (
                <div key={entry.label} className="drilldown-kv-row">
                  <span>{entry.label}</span>
                  <strong>{entry.value}</strong>
                </div>
              ))}
            </div>
            <div className="drilldown-timeline-title">Event Timeline</div>
            <div className="drilldown-timeline">
              {drilldown.timeline.map((entry, index) => (
                <div key={`${entry}-${index}`} className="drilldown-timeline-item">
                  {entry}
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}

      {anyApiError ? (
        <div className="empty-card section-offset">
          <strong>API Data Unavailable</strong>
          <p>Live API mode is enabled, but one or more backend endpoints are unreachable.</p>
        </div>
      ) : null}

      {noApiEntities ? (
        <div className="empty-card section-offset">
          <strong>No Live Data Yet</strong>
          <p>The backend is reachable, but there are currently no providers, jobs, or runs.</p>
        </div>
      ) : null}
    </>
  );
}
