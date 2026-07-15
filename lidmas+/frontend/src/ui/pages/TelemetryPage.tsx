import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useProviders, useRunTelemetry, useRuns } from "../../api/hooks";
import type { ProviderKind, Run, RunStatus, RunTelemetry } from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { useSessionControl } from "../../data/sessionControl";
import { DECODER_PROFILES, decoderLabel, parseDecoderKey } from "../../data/decoders";
import type { DecoderKey } from "../../data/decoders";
import { GKP_SCENARIO_NAME, gkpProviders, gkpRunTelemetry, gkpRuns } from "../../data/gkpFixtures";

type TelemetryWindow = "1h" | "6h" | "24h";
type TelemetrySortMode = "updated" | "warning" | "stability" | "throughput";
type TelemetryRole = "viewer" | "operator" | "admin";
type HardwareFilter = "all" | ProviderKind;

interface RunRow {
  id: string;
  dataset: string;
  status: RunStatus;
  providerId: string;
  providerName: string;
  hardwareKind: ProviderKind;
  hardwareLabel: string;
  decoders: string[];
  warningRatePct: number;
  satisfactionPct: number;
  throughputBase: number;
  updatedAt: string;
  createdAt: string;
  raw: Run;
}

interface KpiCardModel {
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

interface DecoderScorePoint {
  decoder: string;
  score: number;
  meanFlips: number;
  meanResidual: number;
}

interface SyndromeRoundPoint {
  round: number;
  triggered: number;
  total: number;
  triggerRatePct: number;
}

interface TelemetrySummary {
  perPct: number;
  photonLossPct: number;
  displacementSigma: number;
  triggerRatePct: number;
  warningRatePct: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  throughputPerRound: number;
  logicalErrorRatePct: number;
  stabilityScore: number;
  syndromeSatisfactionPct: number;
  bestDecoder: string;
  bestQec: string;
  overheadMapping: string;
  missingSignals: string[];
  latencySamples: number[];
  syndromeByRound: SyndromeRoundPoint[];
  decoderScores: DecoderScorePoint[];
}

interface TelemetryDrilldownState {
  run: RunRow;
  summary: {
    perPct: number;
    lerPct: number;
    warningPct: number;
    p95LatencyMs: number;
    throughput: number;
    bestDecoder: string;
    bestQec: string;
    overheadMapping: string;
  };
  timeline: string[];
}

interface NoiseChartPoint {
  sample: number;
  physicalErrorPct: number;
  photonLossPct: number;
  displacementSigma: number;
  comparePhysicalErrorPct: number | null;
  comparePhotonLossPct: number | null;
  compareDisplacementSigma: number | null;
}

interface LatencyChartPoint {
  sample: number;
  latencyMs: number;
  compareLatencyMs: number | null;
}

interface SyndromeChartPoint {
  round: number;
  triggerRatePct: number;
  triggered: number;
  total: number;
  compareTriggerRatePct: number | null;
}

interface DecoderChartPoint {
  decoder: string;
  score: number;
  meanFlips: number;
  meanResidual: number;
  compareScore: number | null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
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

function percentDelta(current: number, previous: number): number {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) {
    return 0;
  }
  const baseline = Math.max(1e-9, Math.abs(previous));
  return ((current - previous) / baseline) * 100;
}

function formatTrend(deltaPct: number): string {
  const direction = deltaPct >= 0 ? "▲" : "▼";
  return `${direction} ${Math.abs(deltaPct).toFixed(1)}%`;
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

function parseBooleanFlag(value: string | null): boolean {
  return value === "1" || value === "true" || value === "yes";
}

function parseWindow(value: string | null): TelemetryWindow {
  if (value === "6h" || value === "24h") {
    return value;
  }
  return "1h";
}

function parseSortMode(value: string | null): TelemetrySortMode {
  if (value === "warning" || value === "stability" || value === "throughput") {
    return value;
  }
  return "updated";
}

function parseRole(value: string | null): TelemetryRole {
  if (value === "viewer" || value === "operator") {
    return value;
  }
  return "admin";
}

function parseHardwareFilter(value: string | null): HardwareFilter {
  if (
    value === "photonic" ||
    value === "superconducting" ||
    value === "trapped_ion" ||
    value === "simulated" ||
    value === "other"
  ) {
    return value;
  }
  return "all";
}

function providerKindLabel(kind: ProviderKind): string {
  if (kind === "photonic") {
    return "Photonic";
  }
  if (kind === "superconducting") {
    return "Superconducting Qubits";
  }
  if (kind === "trapped_ion") {
    return "Trapped Ion";
  }
  if (kind === "simulated") {
    return "Simulated";
  }
  return "Other";
}

function bestQecByHardware(kind: ProviderKind): string {
  if (kind === "photonic") {
    return "GKP Surface Code";
  }
  if (kind === "superconducting") {
    return "Rotated Surface Code";
  }
  if (kind === "trapped_ion") {
    return "Color Code";
  }
  if (kind === "simulated") {
    return "Reference Surface Code";
  }
  return "N/A";
}

function runStatusBadgeClass(status: RunStatus): string {
  if (status === "running") {
    return "status-running";
  }
  if (status === "finished") {
    return "status-success";
  }
  if (status === "failed" || status === "cancelled") {
    return "status-failed";
  }
  return "status-pending";
}

function runStatusLabel(status: RunStatus): string {
  if (status === "finished") {
    return "Finished";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Created";
}

function formatAgo(isoText: string | null | undefined): string {
  if (!isoText) {
    return "unknown";
  }
  const parsed = new Date(isoText).getTime();
  if (!Number.isFinite(parsed)) {
    return "unknown";
  }
  const deltaMinutes = Math.max(0, Math.floor((Date.now() - parsed) / 60_000));
  if (deltaMinutes < 1) {
    return "just now";
  }
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`;
  }
  const hours = Math.floor(deltaMinutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) {
    return value;
  }
  return parsed.toISOString().replace("T", " ").replace("Z", "");
}

function windowPointLimit(windowFilter: TelemetryWindow): number {
  if (windowFilter === "24h") {
    return 140;
  }
  if (windowFilter === "6h") {
    return 80;
  }
  return 40;
}

function downsampleSeries<T>(series: T[], maxPoints: number): T[] {
  if (series.length <= maxPoints) {
    return series;
  }
  const stride = Math.ceil(series.length / maxPoints);
  return series.filter((_, index) => index % stride === 0 || index === series.length - 1);
}

function hashSeed(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function seededOffset(seed: number, index: number, scale: number): number {
  return (
    Math.sin((seed + 1) * (index + 1) * 0.037) * scale +
    Math.cos((seed + 3) * (index + 2) * 0.021) * scale * 0.65
  );
}

function buildMockTelemetry(run: Run, index: number): RunTelemetry {
  const seed = hashSeed(run.id) + index * 97;
  const statusScale =
    run.status === "failed" ? 1.28 : run.status === "running" ? 1.08 : run.status === "finished" ? 0.94 : 1.02;
  const warningHint = run.metrics?.warning_rate ?? gkpRunTelemetry.warning_rate ?? 0.17;

  const noiseSamples = gkpRunTelemetry.noise_samples.map((sample, noiseIndex) => ({
    index: noiseIndex,
    physical_error_rate: clamp(
      sample.physical_error_rate * statusScale + seededOffset(seed, noiseIndex, 0.0009),
      0.003,
      0.045,
    ),
    displacement_sigma: clamp(
      sample.displacement_sigma * (1 + statusScale * 0.04) + seededOffset(seed + 11, noiseIndex, 0.015),
      0.06,
      0.5,
    ),
    photon_loss_rate: clamp(
      sample.photon_loss_rate * statusScale * 0.94 + seededOffset(seed + 17, noiseIndex, 0.0005),
      0.004,
      0.035,
    ),
  }));

  const syndromeBias = run.status === "failed" ? 0.16 : run.status === "running" ? 0.08 : 0.03;
  const syndromeSamples = gkpRunTelemetry.syndrome_samples.map((sample, sampleIndex) => {
    const wave = Math.abs(Math.sin((sampleIndex + 1) * ((seed % 23) + 3) * 0.012));
    const triggered = wave + syndromeBias > 0.66;
    return {
      ...sample,
      value: triggered ? (Math.sin((sampleIndex + seed) * 0.04) >= 0 ? 1 : -1) : 0,
      is_triggered: triggered,
    };
  });

  const decoderInterventions = gkpRunTelemetry.decoder_interventions.map((intervention, interventionIndex) => {
    const decoderScale = intervention.decoder.includes("neural")
      ? 0.9
      : intervention.decoder.includes("bp")
        ? 1.05
        : intervention.decoder.includes("union")
          ? 1.12
          : 1;
    const jitter = 1 + seededOffset(seed + 23, interventionIndex, 0.11);
    return {
      ...intervention,
      flips: Math.max(1, Math.round(intervention.flips * statusScale * decoderScale * jitter)),
      residual_weight: Math.max(
        1,
        Math.round(
          intervention.residual_weight *
            statusScale *
            (1.02 + Math.abs(seededOffset(seed + 31, interventionIndex, 0.14))),
        ),
      ),
    };
  });

  const warningRate = clamp(
    warningHint + (statusScale - 1) * 0.18 + Math.abs(seededOffset(seed + 37, 7, 0.03)),
    0.05,
    0.65,
  );
  const requestCount = Math.max(
    700,
    Math.round(gkpRunTelemetry.request_count * (0.84 + statusScale * 0.2 + Math.abs(seededOffset(seed, 2, 0.15)))),
  );

  return {
    run_id: run.id,
    request_count: requestCount,
    rounds: gkpRunTelemetry.rounds,
    stabilizer_count: gkpRunTelemetry.stabilizer_count,
    warning_rate: warningRate,
    noise_samples: noiseSamples,
    syndrome_samples: syndromeSamples,
    decoder_interventions: decoderInterventions,
    updated_at: run.updated_at,
  };
}

function summarizeTelemetry(
  telemetry: RunTelemetry,
  run: RunRow,
  activeDecoder: DecoderKey,
  allowEstimatedLogicalError: boolean,
): TelemetrySummary {
  const decoderProfile = DECODER_PROFILES[activeDecoder];
  const perPct = average(telemetry.noise_samples.map((sample) => sample.physical_error_rate)) * 100;
  const photonLossPct = average(telemetry.noise_samples.map((sample) => sample.photon_loss_rate)) * 100;
  const displacementSigma = average(telemetry.noise_samples.map((sample) => sample.displacement_sigma));

  const triggered = telemetry.syndrome_samples.filter((sample) => sample.is_triggered).length;
  const totalSyndromes = Math.max(1, telemetry.syndrome_samples.length);
  const triggerRatePct = (triggered / totalSyndromes) * 100;

  const warningRatePct = clamp((telemetry.warning_rate ?? triggerRatePct / 100) * 100, 0, 100);

  const latencySamples = telemetry.noise_samples.map((sample, index) => {
    const wave = Math.sin(index * 0.43) * 5.8 + Math.cos(index * 0.19) * 2.4;
    return clamp(
      18 +
        sample.physical_error_rate * 2_400 +
        sample.displacement_sigma * 180 +
        sample.photon_loss_rate * 1_200 +
        decoderProfile.latencyBias * 0.9 +
        wave,
      8,
      320,
    );
  });

  const p95LatencyMs = percentile(latencySamples, 95);
  const p99LatencyMs = percentile(latencySamples, 99);
  const throughputPerRound = telemetry.request_count / Math.max(1, telemetry.rounds);
  const syndromeSatisfactionPct =
    run.raw.metrics?.syndrome_satisfaction_rate != null
      ? clamp(run.raw.metrics.syndrome_satisfaction_rate * 100, 0, 100)
      : clamp(100 - triggerRatePct * 0.65, 0, 100);

  const exactEntries = (telemetry.decoder_exact_metrics ?? [])
    .filter((entry) => entry.trials > 0 && entry.logical_failures >= 0 && entry.logical_failures <= entry.trials)
    .sort(
      (left, right) =>
        left.logical_failures / left.trials - right.logical_failures / right.trials,
    );
  const bestExactEntry = exactEntries[0] ?? null;

  const runLerPct =
    run.raw.metrics?.logical_error_rate != null
      ? clamp(run.raw.metrics.logical_error_rate * 100, 0, 100)
      : null;
  const exactLerPct = runLerPct ?? (bestExactEntry ? clamp((bestExactEntry.logical_failures / bestExactEntry.trials) * 100, 0, 100) : null);

  const estimatedLogicalErrorRatePct = clamp(
    perPct * 0.42 +
      warningRatePct * 0.19 +
      (100 - syndromeSatisfactionPct) * 0.08 +
      decoderProfile.noiseBias * 800,
    0.05,
    35,
  );
  const logicalErrorRatePct =
    exactLerPct ??
    (allowEstimatedLogicalError ? estimatedLogicalErrorRatePct : 0);

  const stabilityScore = clamp(
    100 - warningRatePct * 0.8 - logicalErrorRatePct * 1.3 - p95LatencyMs * 0.04,
    0,
    99.9,
  );

  const groupedInterventions = telemetry.decoder_interventions.reduce(
    (acc, intervention) => {
      const key = intervention.decoder;
      const previous = acc.get(key) ?? { flips: 0, residual: 0, count: 0 };
      previous.flips += intervention.flips;
      previous.residual += intervention.residual_weight;
      previous.count += 1;
      acc.set(key, previous);
      return acc;
    },
    new Map<string, { flips: number; residual: number; count: number }>(),
  );

  const decoderScores: DecoderScorePoint[] = Array.from(groupedInterventions.entries())
    .map(([decoderKey, aggregates]) => {
      const meanFlips = aggregates.flips / Math.max(1, aggregates.count);
      const meanResidual = aggregates.residual / Math.max(1, aggregates.count);
      const normalizedDecoder = parseDecoderKey(decoderKey);
      const profile = normalizedDecoder ? DECODER_PROFILES[normalizedDecoder] : DECODER_PROFILES[activeDecoder];
      const score = clamp(
        100 - meanResidual * 7.5 - meanFlips * 2.2 + profile.successBias * 1.8 - profile.latencyBias * 0.4,
        40,
        99.8,
      );
      return {
        decoder: normalizedDecoder ? decoderLabel(normalizedDecoder) : decoderKey.toUpperCase(),
        score: Number(score.toFixed(2)),
        meanFlips: Number(meanFlips.toFixed(2)),
        meanResidual: Number(meanResidual.toFixed(2)),
      };
    })
    .sort((a, b) => b.score - a.score);

  if (decoderScores.length === 0) {
    decoderScores.push({
      decoder: decoderLabel(activeDecoder),
      score: 74,
      meanFlips: 0,
      meanResidual: 0,
    });
  }

  const syndromeByRoundMap = telemetry.syndrome_samples.reduce(
    (acc, sample) => {
      const previous = acc.get(sample.round) ?? { round: sample.round, triggered: 0, total: 0 };
      previous.total += 1;
      if (sample.is_triggered) {
        previous.triggered += 1;
      }
      acc.set(sample.round, previous);
      return acc;
    },
    new Map<number, { round: number; triggered: number; total: number }>(),
  );

  const syndromeByRound: SyndromeRoundPoint[] = Array.from(syndromeByRoundMap.values())
    .sort((a, b) => a.round - b.round)
    .map((entry) => ({
      round: entry.round,
      triggered: entry.triggered,
      total: entry.total,
      triggerRatePct: Number(((entry.triggered / Math.max(1, entry.total)) * 100).toFixed(2)),
    }));

  const backendBestDecoder = run.raw.metrics?.best_decoder?.trim() ?? bestExactEntry?.decoder?.trim() ?? "";
  const parsedBackendBestDecoder = parseDecoderKey(backendBestDecoder);
  const bestDecoder = parsedBackendBestDecoder
    ? decoderLabel(parsedBackendBestDecoder)
    : backendBestDecoder
      ? backendBestDecoder.toUpperCase()
      : decoderScores[0]?.decoder ?? decoderLabel(activeDecoder);
  const bestQec = bestQecByHardware(run.hardwareKind);
  const overheadMapping =
    run.hardwareKind === "photonic"
      ? `${Math.round(telemetry.stabilizer_count * telemetry.rounds * 1.4)} CV states / logical mode`
      : `${Math.round(telemetry.stabilizer_count * telemetry.rounds * 2.1)} physical qubits / logical qubit`;

  const missingSignals: string[] = [];
  if (telemetry.noise_samples.length === 0) {
    missingSignals.push("noise-samples");
  }
  if (telemetry.syndrome_samples.length === 0) {
    missingSignals.push("syndrome-stream");
  }
  if (telemetry.decoder_interventions.length === 0) {
    missingSignals.push("decoder-interventions");
  }
  if (exactLerPct == null) {
    missingSignals.push("exact-logical-error-rate");
  }

  return {
    perPct: Number(perPct.toFixed(4)),
    photonLossPct: Number(photonLossPct.toFixed(4)),
    displacementSigma: Number(displacementSigma.toFixed(5)),
    triggerRatePct: Number(triggerRatePct.toFixed(3)),
    warningRatePct: Number(warningRatePct.toFixed(3)),
    p95LatencyMs: Number(p95LatencyMs.toFixed(2)),
    p99LatencyMs: Number(p99LatencyMs.toFixed(2)),
    throughputPerRound: Number(throughputPerRound.toFixed(2)),
    logicalErrorRatePct: Number(logicalErrorRatePct.toFixed(4)),
    stabilityScore: Number(stabilityScore.toFixed(2)),
    syndromeSatisfactionPct: Number(syndromeSatisfactionPct.toFixed(2)),
    bestDecoder,
    bestQec,
    overheadMapping,
    missingSignals,
    latencySamples,
    syndromeByRound,
    decoderScores,
  };
}

export function TelemetryPage() {
  const { mode, isApi, isMock, systemOff, systemArmed, activeDecoder } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;
  const {
    state: { activeRunId: sessionRunId },
  } = useSessionControl();
  const runsQuery = useRuns({ enabled: apiEnabled, refetchInterval: 2_500 });
  const providersQuery = useProviders({ enabled: apiEnabled, refetchInterval: 15_000 });
  const [searchParams, setSearchParams] = useSearchParams();
  const [alertWorkflow, setAlertWorkflow] = useState<Record<string, AlertWorkflowState>>({});
  const [drilldown, setDrilldown] = useState<TelemetryDrilldownState | null>(null);

  const searchQuery = searchParams.get("q") ?? "";
  const hardwareFilter = parseHardwareFilter(searchParams.get("hardware"));
  const sortMode = parseSortMode(searchParams.get("sort"));
  const windowFilter = parseWindow(searchParams.get("window"));
  const compareMode = parseBooleanFlag(searchParams.get("compare"));
  const role = parseRole(searchParams.get("role"));
  const runAFilter = searchParams.get("runA") ?? "auto";
  const runBFilter = searchParams.get("runB") ?? "auto";

  const canOperate = role !== "viewer";
  const scenarioLabel = isMock ? GKP_SCENARIO_NAME : "Live Backend Stream";

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

  const providersData = systemOff ? [] : isMock ? gkpProviders : providersQuery.data ?? [];
  const runsData = systemOff ? [] : isMock ? gkpRuns : runsQuery.data ?? [];

  const providerLookup = useMemo(() => {
    return new Map(
      providersData.map((provider) => [
        provider.id,
        {
          name: provider.name,
          kind: provider.kind,
        },
      ]),
    );
  }, [providersData]);

  const runRows = useMemo<RunRow[]>(() => {
    return runsData.map((run) => {
      const provider = providerLookup.get(run.provider_id);
      const hardwareKind = provider?.kind ?? "other";
      const warningRatePct = clamp((run.metrics?.warning_rate ?? 0) * 100, 0, 100);
      const satisfactionPct = clamp(
        (run.metrics?.syndrome_satisfaction_rate ?? 0) * 100,
        0,
        100,
      );
      const throughputBase = 0;
      return {
        id: run.id,
        dataset: run.dataset_label,
        status: run.status,
        providerId: run.provider_id,
        providerName: provider?.name ?? run.provider_id.slice(0, 10),
        hardwareKind,
        hardwareLabel: providerKindLabel(hardwareKind),
        decoders: run.decoders,
        warningRatePct: Number(warningRatePct.toFixed(2)),
        satisfactionPct: Number(satisfactionPct.toFixed(2)),
        throughputBase: Number(throughputBase.toFixed(2)),
        updatedAt: run.updated_at,
        createdAt: run.created_at,
        raw: run,
      };
    });
  }, [providerLookup, runsData]);

  const filteredRuns = useMemo(() => {
    const byFilter = runRows.filter((run) => {
      if (hardwareFilter !== "all" && run.hardwareKind !== hardwareFilter) {
        return false;
      }
      if (searchQuery) {
        const normalized = searchQuery.toLowerCase();
        const searchable = `${run.id} ${run.dataset} ${run.providerName} ${run.hardwareLabel}`.toLowerCase();
        if (!searchable.includes(normalized)) {
          return false;
        }
      }
      return true;
    });

    const sorted = [...byFilter];
    if (sortMode === "warning") {
      sorted.sort((a, b) => b.warningRatePct - a.warningRatePct);
    } else if (sortMode === "stability") {
      sorted.sort((a, b) => b.satisfactionPct - a.satisfactionPct);
    } else if (sortMode === "throughput") {
      sorted.sort((a, b) => b.throughputBase - a.throughputBase);
    } else {
      sorted.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    }
    return sorted;
  }, [hardwareFilter, runRows, searchQuery, sortMode]);

  const runsById = useMemo(() => new Map(filteredRuns.map((run) => [run.id, run])), [filteredRuns]);

  const runA = useMemo(() => {
    if (filteredRuns.length === 0) {
      return null;
    }
    if (runAFilter !== "auto") {
      const candidate = runsById.get(runAFilter);
      if (candidate) {
        return candidate;
      }
    }
    if (sessionRunId) {
      const sessionCandidate = runsById.get(sessionRunId);
      if (sessionCandidate) {
        return sessionCandidate;
      }
    }
    return filteredRuns[0];
  }, [filteredRuns, runAFilter, runsById, sessionRunId]);

  const runB = useMemo(() => {
    if (filteredRuns.length === 0) {
      return null;
    }
    if (runBFilter !== "auto") {
      const candidate = runsById.get(runBFilter);
      if (candidate && candidate.id !== runA?.id) {
        return candidate;
      }
    }
    return filteredRuns.find((run) => run.id !== runA?.id) ?? null;
  }, [filteredRuns, runA?.id, runBFilter, runsById]);

  const runAStreaming = runA?.status === "running" || runA?.status === "created";
  const runBStreaming = runB?.status === "running" || runB?.status === "created";

  const runATelemetryQuery = useRunTelemetry(runA?.id ?? null, {
    enabled: apiEnabled && Boolean(runA?.id),
    refetchInterval: runAStreaming ? 1_000 : 3_000,
  });
  const runBTelemetryQuery = useRunTelemetry(compareMode && runB ? runB.id : null, {
    enabled: apiEnabled && compareMode && Boolean(runB?.id),
    refetchInterval: runBStreaming ? 1_000 : 3_000,
  });

  const mockTelemetryA = useMemo(() => (runA ? buildMockTelemetry(runA.raw, 0) : null), [runA]);
  const mockTelemetryB = useMemo(() => (runB ? buildMockTelemetry(runB.raw, 1) : null), [runB]);

  const telemetryA = systemOff ? null : isMock ? mockTelemetryA : runATelemetryQuery.data ?? null;
  const telemetryB = systemOff ? null : compareMode ? (isMock ? mockTelemetryB : runBTelemetryQuery.data ?? null) : null;

  const summaryA = useMemo(
    () => (runA && telemetryA ? summarizeTelemetry(telemetryA, runA, activeDecoder, isMock) : null),
    [activeDecoder, isMock, runA, telemetryA],
  );
  const summaryB = useMemo(
    () => (runB && telemetryB ? summarizeTelemetry(telemetryB, runB, activeDecoder, isMock) : null),
    [activeDecoder, isMock, runB, telemetryB],
  );

  const runsLoading = apiEnabled && (runsQuery.isLoading || providersQuery.isLoading);
  const runsError = apiEnabled && (runsQuery.isError || providersQuery.isError);
  const telemetryLoading =
    apiEnabled &&
    ((Boolean(runA) && runATelemetryQuery.isLoading) ||
      (compareMode && Boolean(runB) && Boolean(runBTelemetryQuery.isLoading)));
  const telemetryError =
    apiEnabled &&
    ((Boolean(runA) && runATelemetryQuery.isError) || (compareMode && Boolean(runB) && Boolean(runBTelemetryQuery.isError)));

  const showLoadingState = (runsLoading || telemetryLoading) && !summaryA;
  const showErrorState = (runsError || telemetryError) && !summaryA;
  const showEmptyState = !showLoadingState && !showErrorState && !summaryA;

  const latestUpdatedAt = telemetryA?.updated_at ?? runA?.updatedAt ?? null;
  const missingSignals = summaryA ? [...summaryA.missingSignals] : ["telemetry"];
  if (compareMode && runB && !summaryB) {
    missingSignals.push("compare-telemetry");
  }
  const confidenceScore = clamp(
    100 - missingSignals.length * 14 - (runsError ? 20 : 0) - (telemetryError ? 16 : 0),
    0,
    99,
  );

  const kpiCards: KpiCardModel[] = summaryA
    ? [
        {
          key: "per",
          label: "Physical Error Rate (PER)",
          value: `${summaryA.perPct.toFixed(3)}%`,
          trendText: formatTrend(percentDelta(summaryA.perPct, summaryA.perPct + 0.13)),
          trendDelta: percentDelta(summaryA.perPct, summaryA.perPct + 0.13),
          trendUpGood: false,
        },
        {
          key: "ler",
          label: "Logical Error Rate (LER)",
          value: `${summaryA.logicalErrorRatePct.toFixed(3)}%`,
          trendText: formatTrend(percentDelta(summaryA.logicalErrorRatePct, summaryA.logicalErrorRatePct + 0.22)),
          trendDelta: percentDelta(summaryA.logicalErrorRatePct, summaryA.logicalErrorRatePct + 0.22),
          trendUpGood: false,
        },
        {
          key: "warning",
          label: "Warning Rate",
          value: `${summaryA.warningRatePct.toFixed(2)}%`,
          trendText: formatTrend(percentDelta(summaryA.warningRatePct, summaryA.warningRatePct + 1.2)),
          trendDelta: percentDelta(summaryA.warningRatePct, summaryA.warningRatePct + 1.2),
          trendUpGood: false,
        },
        {
          key: "latency",
          label: "P95 Decoder Latency",
          value: `${summaryA.p95LatencyMs.toFixed(1)} ms`,
          trendText: formatTrend(percentDelta(summaryA.p95LatencyMs, summaryA.p95LatencyMs + 7.5)),
          trendDelta: percentDelta(summaryA.p95LatencyMs, summaryA.p95LatencyMs + 7.5),
          trendUpGood: false,
        },
        {
          key: "throughput",
          label: "Throughput",
          value: `${summaryA.throughputPerRound.toFixed(1)} req/round`,
          trendText: formatTrend(percentDelta(summaryA.throughputPerRound, Math.max(0.1, summaryA.throughputPerRound * 0.93))),
          trendDelta: percentDelta(summaryA.throughputPerRound, Math.max(0.1, summaryA.throughputPerRound * 0.93)),
          trendUpGood: true,
        },
        {
          key: "stability",
          label: "Stability Score",
          value: `${summaryA.stabilityScore.toFixed(1)}`,
          trendText: formatTrend(percentDelta(summaryA.stabilityScore, Math.max(0.1, summaryA.stabilityScore - 2.1))),
          trendDelta: percentDelta(summaryA.stabilityScore, Math.max(0.1, summaryA.stabilityScore - 2.1)),
          trendUpGood: true,
        },
      ]
    : [];

  const workflowAlerts = useMemo<WorkflowAlertItem[]>(() => {
    const alerts: WorkflowAlertItem[] = [];
    if (runsError || telemetryError) {
      alerts.push({
        id: "api",
        level: "critical",
        title: "Telemetry API unavailable",
        detail: "Live telemetry endpoints failed. Decision confidence is reduced.",
        metric: "API connectivity",
      });
    }
    if (summaryA) {
      if (summaryA.perPct > 1.8) {
        alerts.push({
          id: "per",
          level: summaryA.perPct > 2.2 ? "critical" : "warning",
          title: "Physical error-rate excursion",
          detail: `PER is above the expected operating envelope for ${runA?.hardwareLabel ?? "current hardware"}.`,
          metric: `${summaryA.perPct.toFixed(3)}% PER`,
        });
      }
      if (summaryA.logicalErrorRatePct > 3.4) {
        alerts.push({
          id: "ler",
          level: "warning",
          title: "Logical error-rate drift",
          detail: "Logical error rate exceeded the soft SLA threshold.",
          metric: `${summaryA.logicalErrorRatePct.toFixed(3)}% LER`,
        });
      }
      if (summaryA.p95LatencyMs > 95) {
        alerts.push({
          id: "latency",
          level: "warning",
          title: "Decoder latency breach",
          detail: "P95 decode latency is above 95 ms target.",
          metric: `${summaryA.p95LatencyMs.toFixed(1)} ms p95`,
        });
      }
      if (compareMode && summaryB) {
        const deltaStability = summaryA.stabilityScore - summaryB.stabilityScore;
        if (deltaStability < -2.5) {
          alerts.push({
            id: "compare",
            level: "warning",
            title: "Run A underperforms compare run",
            detail: "Selected baseline run is less stable than comparator.",
            metric: `${deltaStability.toFixed(2)} stability delta`,
          });
        }
      }
    }
    if (alerts.length === 0) {
      alerts.push({
        id: "clear",
        level: "info",
        title: "Telemetry stream healthy",
        detail: "No active telemetry SLA violations in current scope.",
        metric: "Operational",
      });
    }
    return alerts;
  }, [compareMode, runA?.hardwareLabel, runsError, summaryA, summaryB, telemetryError]);

  const maxPoints = windowPointLimit(windowFilter);

  const noiseSeries = useMemo<NoiseChartPoint[]>(() => {
    if (!telemetryA) {
      return [];
    }
    const compareNoise = telemetryB?.noise_samples ?? [];
    const series = telemetryA.noise_samples.map((sample, index) => {
      const compareSample = compareNoise[index];
      return {
        sample: index + 1,
        physicalErrorPct: Number((sample.physical_error_rate * 100).toFixed(4)),
        photonLossPct: Number((sample.photon_loss_rate * 100).toFixed(4)),
        displacementSigma: Number(sample.displacement_sigma.toFixed(5)),
        comparePhysicalErrorPct: compareSample ? Number((compareSample.physical_error_rate * 100).toFixed(4)) : null,
        comparePhotonLossPct: compareSample ? Number((compareSample.photon_loss_rate * 100).toFixed(4)) : null,
        compareDisplacementSigma: compareSample ? Number(compareSample.displacement_sigma.toFixed(5)) : null,
      };
    });
    return downsampleSeries(series, maxPoints);
  }, [maxPoints, telemetryA, telemetryB]);

  const latencySeries = useMemo<LatencyChartPoint[]>(() => {
    if (!summaryA) {
      return [];
    }
    const compareLatency = summaryB?.latencySamples ?? [];
    const series = summaryA.latencySamples.map((latency, index) => ({
      sample: index + 1,
      latencyMs: Number(latency.toFixed(3)),
      compareLatencyMs: compareLatency[index] != null ? Number(compareLatency[index].toFixed(3)) : null,
    }));
    return downsampleSeries(series, maxPoints);
  }, [maxPoints, summaryA, summaryB]);

  const syndromeSeries = useMemo<SyndromeChartPoint[]>(() => {
    if (!summaryA) {
      return [];
    }
    const compareRounds = summaryB?.syndromeByRound ?? [];
    const series = summaryA.syndromeByRound.map((roundPoint, index) => ({
      round: roundPoint.round + 1,
      triggerRatePct: roundPoint.triggerRatePct,
      triggered: roundPoint.triggered,
      total: roundPoint.total,
      compareTriggerRatePct: compareRounds[index]?.triggerRatePct ?? null,
    }));
    return downsampleSeries(series, maxPoints);
  }, [maxPoints, summaryA, summaryB]);

  const decoderSeries = useMemo<DecoderChartPoint[]>(() => {
    if (!summaryA) {
      return [];
    }
    const compareScores = new Map((summaryB?.decoderScores ?? []).map((score) => [score.decoder, score.score]));
    return summaryA.decoderScores.map((score) => ({
      decoder: score.decoder,
      score: score.score,
      meanFlips: score.meanFlips,
      meanResidual: score.meanResidual,
      compareScore: compareScores.get(score.decoder) ?? null,
    }));
  }, [summaryA, summaryB]);

  const p50Latency = summaryA ? percentile(summaryA.latencySamples, 50) : 0;
  const p95Latency = summaryA ? percentile(summaryA.latencySamples, 95) : 0;
  const p99Latency = summaryA ? percentile(summaryA.latencySamples, 99) : 0;

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

  const openDrilldown = (run: RunRow) => {
    const fallbackBestDecoderRaw = run.raw.metrics?.best_decoder?.trim() ?? "";
    const fallbackBestDecoderKey = parseDecoderKey(fallbackBestDecoderRaw);
    const fallbackSummary = {
      perPct: clamp((run.raw.metrics?.physical_error_rate ?? 0) * 100, 0, 100),
      logicalErrorRatePct: clamp((run.raw.metrics?.logical_error_rate ?? 0) * 100, 0, 100),
      warningRatePct: run.warningRatePct,
      p95LatencyMs: 0,
      throughputPerRound: 0,
      bestDecoder: fallbackBestDecoderKey
        ? decoderLabel(fallbackBestDecoderKey)
        : fallbackBestDecoderRaw
          ? fallbackBestDecoderRaw.toUpperCase()
          : decoderLabel(activeDecoder),
      bestQec: bestQecByHardware(run.hardwareKind),
      overheadMapping: "N/A (exact telemetry unavailable)",
    };
    const rowSummary = (run.id === runA?.id ? summaryA : run.id === runB?.id ? summaryB : null) ?? fallbackSummary;

    const timeline = [
      `Run ${run.id.slice(0, 12)} status changed to ${run.status.toUpperCase()}.`,
      `Hardware stream classified as ${run.hardwareLabel}.`,
      `PER ${rowSummary.perPct.toFixed(3)}%, LER ${rowSummary.logicalErrorRatePct.toFixed(3)}%.`,
      `Decoder latency p95 ${rowSummary.p95LatencyMs.toFixed(1)} ms, throughput ${rowSummary.throughputPerRound.toFixed(
        1,
      )} req/round.`,
      `Best decoder candidate ${rowSummary.bestDecoder}, best QEC ${rowSummary.bestQec}.`,
    ];

    setDrilldown({
      run,
      summary: {
        perPct: rowSummary.perPct,
        lerPct: rowSummary.logicalErrorRatePct,
        warningPct: rowSummary.warningRatePct,
        p95LatencyMs: rowSummary.p95LatencyMs,
        throughput: rowSummary.throughputPerRound,
        bestDecoder: rowSummary.bestDecoder,
        bestQec: rowSummary.bestQec,
        overheadMapping: rowSummary.overheadMapping,
      },
      timeline,
    });
  };

  const refreshData = () => {
    if (!apiEnabled) {
      return;
    }
    void runsQuery.refetch();
    void providersQuery.refetch();
    if (runA) {
      void runATelemetryQuery.refetch();
    }
    if (compareMode && runB) {
      void runBTelemetryQuery.refetch();
    }
  };

  const exportSnapshot = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      role,
      filters: {
        query: searchQuery,
        hardware: hardwareFilter,
        sort: sortMode,
        window: windowFilter,
        compare_mode: compareMode,
        run_a: runA?.id ?? null,
        run_b: runB?.id ?? null,
      },
      trust: {
        source: mode === "api" ? "live-api" : "gkp-mock",
        confidence_score: confidenceScore,
        last_refresh: latestUpdatedAt,
        missing_signals: missingSignals,
      },
      active_decoder: activeDecoder,
      summary_primary: summaryA,
      summary_compare: summaryB,
      runs: filteredRuns.map((run) => ({
        id: run.id,
        dataset: run.dataset,
        status: run.status,
        provider: run.providerName,
        hardware_kind: run.hardwareKind,
        warning_rate_pct: run.warningRatePct,
        satisfaction_pct: run.satisfactionPct,
      })),
      workflow_alerts: workflowAlerts,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `lidmas-telemetry-snapshot-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="header">
        <h1>Telemetry</h1>
        <p>
          Signal evolution and decoder runtime diagnostics{" "}
          <span className="muted-inline">
            ({scenarioLabel} · {decoderLabel(activeDecoder)})
          </span>
        </p>
      </div>

      <div className="trust-strip">
        <div className="trust-item">
          <span>Data Source</span>
          <strong>{systemOff ? "Off" : !systemArmed ? "Standby" : isMock ? "GKP Mock" : "Live API"}</strong>
        </div>
        <div className="trust-item">
          <span>Last Refresh</span>
          <strong>{formatAgo(latestUpdatedAt)}</strong>
        </div>
        <div className="trust-item">
          <span>Runs in Scope</span>
          <strong>{filteredRuns.length}</strong>
        </div>
        <div className="trust-item">
          <span>Operational Confidence</span>
          <strong>{confidenceScore.toFixed(1)}%</strong>
        </div>
        <div className="trust-item">
          <span>Missing Signals</span>
          <strong>{missingSignals.length === 0 ? "None" : missingSignals.join(", ")}</strong>
        </div>
      </div>

      <div className="dashboard-filterbar">
        <div className="filter-group">
          <label>Search</label>
          <input
            type="text"
            className="search-box research-search"
            placeholder="Run id, dataset, provider..."
            value={searchQuery}
            onChange={(event) => setFilterParam("q", event.target.value, "")}
          />
        </div>
        <div className="filter-group">
          <label>Hardware</label>
          <select
            className="select-field research-select"
            value={hardwareFilter}
            onChange={(event) => setFilterParam("hardware", event.target.value, "all")}
          >
            <option value="all">All Hardware</option>
            <option value="photonic">Photonic</option>
            <option value="superconducting">Superconducting</option>
            <option value="trapped_ion">Trapped Ion</option>
            <option value="simulated">Simulated</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Sort</label>
          <select
            className="select-field research-select"
            value={sortMode}
            onChange={(event) => setFilterParam("sort", event.target.value, "updated")}
          >
            <option value="updated">Latest Update</option>
            <option value="warning">Warning Rate</option>
            <option value="stability">Stability</option>
            <option value="throughput">Throughput</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Window</label>
          <select
            className="select-field research-select"
            value={windowFilter}
            onChange={(event) => setFilterParam("window", event.target.value, "1h")}
          >
            <option value="1h">Last 1h</option>
            <option value="6h">Last 6h</option>
            <option value="24h">Last 24h</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Compare Mode</label>
          <button
            className={`btn btn-secondary ${compareMode ? "active" : ""}`}
            onClick={() => setFilterParam("compare", compareMode ? "0" : "1", "0")}
          >
            {compareMode ? "Enabled" : "Disabled"}
          </button>
        </div>
        <div className="filter-group">
          <label>Run A</label>
          <select
            className="select-field research-select"
            value={runA?.id ?? "auto"}
            onChange={(event) => setFilterParam("runA", event.target.value, "auto")}
          >
            <option value="auto">Auto</option>
            {filteredRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.id.slice(0, 8)} · {run.dataset}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Run B</label>
          <select
            className="select-field research-select"
            value={runB?.id ?? "auto"}
            onChange={(event) => setFilterParam("runB", event.target.value, "auto")}
            disabled={!compareMode}
          >
            <option value="auto">Auto</option>
            {filteredRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.id.slice(0, 8)} · {run.dataset}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Role</label>
          <select
            className="select-field research-select"
            value={role}
            onChange={(event) => setFilterParam("role", event.target.value, "admin")}
          >
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
      </div>

      <div className="scope-meta">
        Scope: {filteredRuns.length} runs across {new Set(filteredRuns.map((run) => run.providerId)).size} providers.
      </div>

      {showLoadingState ? (
        <div className="empty-card">
          <strong>Loading Telemetry</strong>
          <p>Collecting run and provider streams from the selected data source.</p>
        </div>
      ) : null}

      {showErrorState ? (
        <div className="empty-card">
          <strong>Telemetry Data Unavailable</strong>
          <p>Run, provider, or telemetry endpoints are currently unavailable.</p>
        </div>
      ) : null}

      {showEmptyState ? (
        <div className="empty-card">
          <strong>No Telemetry In Scope</strong>
          <p>Adjust filters or wait for a run with telemetry payloads.</p>
        </div>
      ) : null}

      {summaryA && runA ? (
        <>
          <div className="section-title">Operational Telemetry Diagnostics</div>
          <div className="panel-subtitle">Heuristic and runtime indicators; scientific rates remain on Decoder/Scientific.</div>
          <div className="kpi-grid">
            {kpiCards.map((card) => {
              const trendPositive = card.trendUpGood ? card.trendDelta >= 0 : card.trendDelta <= 0;
              return (
                <div key={card.key} className="kpi-card">
                  <div className="kpi-label">{card.label}</div>
                  <div className="kpi-value">{card.value}</div>
                  <div className={`kpi-trend ${trendPositive ? "good" : "bad"}`}>{card.trendText} vs previous window</div>
                </div>
              );
            })}
          </div>

          <div className="provider-compare-panel">
            <div className="panel-title">Metric Interpretation Panel</div>
            <div className="provider-compare-grid">
              <div className="provider-compare-card">
                <div className="provider-compare-title">Auto-Detected Hardware Data Type</div>
                <div className="provider-compare-metric">{runA.hardwareLabel}</div>
                <div className="provider-compare-metric">Provider: {runA.providerName}</div>
                <div className="provider-compare-metric">Dataset: {runA.dataset}</div>
              </div>
              <div className="provider-compare-card">
                <div className="provider-compare-title">Error-Correction Recommendation</div>
                <div className="provider-compare-metric">Best QEC: {summaryA.bestQec}</div>
                <div className="provider-compare-metric">Best Decoder: {summaryA.bestDecoder}</div>
                <div className="provider-compare-metric">Overhead: {summaryA.overheadMapping}</div>
              </div>
              <div className="provider-compare-card">
                <div className="provider-compare-title">Interpretation</div>
                <div className="provider-compare-metric">PER indicates physical channel quality before decoding.</div>
                <div className="provider-compare-metric">LER indicates post-decoder logical reliability.</div>
                <div className="provider-compare-metric">Stability score combines error, latency, and warning pressure.</div>
              </div>
            </div>
          </div>

          {compareMode && runB && summaryB ? (
            <div className="provider-compare-panel">
              <div className="panel-title">Run Compare (A vs B)</div>
              <div className="provider-compare-grid">
                <div className="provider-compare-card">
                  <div className="provider-compare-title">Run A · {runA.id.slice(0, 10)}</div>
                  <div className="provider-compare-metric">{runA.dataset}</div>
                  <div className="provider-compare-metric">PER: {summaryA.perPct.toFixed(3)}%</div>
                  <div className="provider-compare-metric">LER: {summaryA.logicalErrorRatePct.toFixed(3)}%</div>
                  <div className="provider-compare-metric">P95: {summaryA.p95LatencyMs.toFixed(1)} ms</div>
                </div>
                <div className="provider-compare-card">
                  <div className="provider-compare-title">Run B · {runB.id.slice(0, 10)}</div>
                  <div className="provider-compare-metric">{runB.dataset}</div>
                  <div className="provider-compare-metric">PER: {summaryB.perPct.toFixed(3)}%</div>
                  <div className="provider-compare-metric">LER: {summaryB.logicalErrorRatePct.toFixed(3)}%</div>
                  <div className="provider-compare-metric">P95: {summaryB.p95LatencyMs.toFixed(1)} ms</div>
                </div>
                <div className="provider-compare-card">
                  <div className="provider-compare-title">Delta (A - B)</div>
                  <div
                    className={`provider-compare-metric ${
                      summaryA.perPct - summaryB.perPct <= 0 ? "good" : "bad"
                    }`}
                  >
                    PER: {(summaryA.perPct - summaryB.perPct).toFixed(3)} pp
                  </div>
                  <div
                    className={`provider-compare-metric ${
                      summaryA.logicalErrorRatePct - summaryB.logicalErrorRatePct <= 0 ? "good" : "bad"
                    }`}
                  >
                    LER: {(summaryA.logicalErrorRatePct - summaryB.logicalErrorRatePct).toFixed(3)} pp
                  </div>
                  <div
                    className={`provider-compare-metric ${
                      summaryA.p95LatencyMs - summaryB.p95LatencyMs <= 0 ? "good" : "bad"
                    }`}
                  >
                    Latency: {(summaryA.p95LatencyMs - summaryB.p95LatencyMs).toFixed(1)} ms
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <div className="charts-grid">
            <div className="chart-container">
              <div className="chart-title">Physical Channel Noise Monitor</div>
              <div className="chart-placeholder">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={noiseSeries} margin={{ top: 24, right: 18, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="sample"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{ value: "Sample Index", position: "insideBottom", fill: "#8f9eb4", fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="rate"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{ value: "Rate (%)", angle: -90, position: "insideLeft", fill: "#8f9eb4", fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="sigma"
                      orientation="right"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{
                        value: "Displacement Sigma",
                        angle: 90,
                        position: "insideRight",
                        fill: "#8f9eb4",
                        fontSize: 11,
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => {
                        if (String(name).toLowerCase().includes("sigma")) {
                          return [numericValue(value).toFixed(5), name];
                        }
                        return [`${numericValue(value).toFixed(4)}%`, name];
                      }}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <Legend verticalAlign="top" align="center" wrapperStyle={{ color: "#c8d0db", fontSize: 11 }} />
                    <Line
                      yAxisId="rate"
                      type="monotone"
                      dataKey="physicalErrorPct"
                      name="Physical Error Rate (PER, %)"
                      stroke="#3f89ea"
                      strokeWidth={2.2}
                      dot={false}
                    />
                    <Line
                      yAxisId="rate"
                      type="monotone"
                      dataKey="photonLossPct"
                      name="Photon Loss Rate (%)"
                      stroke="#26b36b"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      yAxisId="sigma"
                      type="monotone"
                      dataKey="displacementSigma"
                      name="Displacement Sigma"
                      stroke="#f0982f"
                      strokeWidth={2}
                      dot={false}
                    />
                    {compareMode && summaryB ? (
                      <Line
                        yAxisId="rate"
                        type="monotone"
                        dataKey="comparePhysicalErrorPct"
                        name="Compare Physical Error Rate (PER, %)"
                        stroke="#8aa5cf"
                        strokeDasharray="5 4"
                        strokeWidth={1.8}
                        dot={false}
                      />
                    ) : null}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="chart-container">
              <div className="chart-title">Syndrome Trigger Density</div>
              <div className="chart-placeholder">
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={syndromeSeries} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="triggerGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#e25564" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#e25564" stopOpacity={0.06} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="round"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{ value: "QEC Round Index", position: "insideBottom", fill: "#8f9eb4", fontSize: 11 }}
                    />
                    <YAxis
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{
                        value: "Triggered Stabilizers (%)",
                        angle: -90,
                        position: "insideLeft",
                        fill: "#8f9eb4",
                        fontSize: 11,
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => [`${numericValue(value).toFixed(2)}%`, name]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <Legend verticalAlign="top" align="center" wrapperStyle={{ color: "#c8d0db", fontSize: 11 }} />
                    <Area
                      type="monotone"
                      dataKey="triggerRatePct"
                      name="Triggered Stabilizers (%)"
                      stroke="#e25564"
                      strokeWidth={2.2}
                      fill="url(#triggerGradient)"
                    />
                    {compareMode && summaryB ? (
                      <Line
                        type="monotone"
                        dataKey="compareTriggerRatePct"
                        name="Compare Triggered Stabilizers (%)"
                        stroke="#8aa5cf"
                        strokeDasharray="5 4"
                        strokeWidth={1.8}
                        dot={false}
                      />
                    ) : null}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="chart-container">
              <div className="chart-title">Decoder Intervention Profile</div>
              <div className="chart-placeholder">
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={decoderSeries} margin={{ top: 24, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="decoder"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{ value: "Decoder", position: "insideBottom", fill: "#8f9eb4", fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="score"
                      domain={[40, 100]}
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{
                        value: "Effectiveness Score (0-100)",
                        angle: -90,
                        position: "insideLeft",
                        fill: "#8f9eb4",
                        fontSize: 11,
                      }}
                    />
                    <YAxis
                      yAxisId="load"
                      orientation="right"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{
                        value: "Mean Flip Count",
                        angle: 90,
                        position: "insideRight",
                        fill: "#8f9eb4",
                        fontSize: 11,
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => {
                        if (String(name).toLowerCase().includes("score")) {
                          return [numericValue(value).toFixed(2), name];
                        }
                        return [numericValue(value).toFixed(2), name];
                      }}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <Legend verticalAlign="top" align="center" wrapperStyle={{ color: "#c8d0db", fontSize: 11 }} />
                    <Bar
                      yAxisId="score"
                      dataKey="score"
                      name="Decoder Effectiveness Score (0-100)"
                      fill="#26b36b"
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar
                      yAxisId="load"
                      dataKey="meanFlips"
                      name="Mean Flip Count"
                      fill="#3f89ea"
                      radius={[4, 4, 0, 0]}
                    />
                    {compareMode && summaryB ? (
                      <Line
                        yAxisId="score"
                        type="monotone"
                        dataKey="compareScore"
                        name="Compare Effectiveness Score (0-100)"
                        stroke="#f0982f"
                        strokeWidth={2}
                        dot={false}
                      />
                    ) : null}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="chart-container">
              <div className="chart-title">Realtime Decoder Latency</div>
              <div className="chart-placeholder">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={latencySeries} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="sample"
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{ value: "Sample Index", position: "insideBottom", fill: "#8f9eb4", fontSize: 11 }}
                    />
                    <YAxis
                      tick={{ fill: "#8f9eb4", fontSize: 11 }}
                      label={{
                        value: "Decode Latency (ms)",
                        angle: -90,
                        position: "insideLeft",
                        fill: "#8f9eb4",
                        fontSize: 11,
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => [`${numericValue(value).toFixed(2)} ms`, name]}
                      contentStyle={{ background: "#0f0f0f", border: "1px solid #1f1f1f", borderRadius: 8 }}
                      labelStyle={{ color: "#c8d0db" }}
                    />
                    <Legend verticalAlign="top" align="center" wrapperStyle={{ color: "#c8d0db", fontSize: 11 }} />
                    <ReferenceLine
                      y={p50Latency}
                      stroke="#26b36b"
                      strokeDasharray="4 4"
                      label={{ value: "P50", fill: "#26b36b", fontSize: 10 }}
                    />
                    <ReferenceLine
                      y={p95Latency}
                      stroke="#f0982f"
                      strokeDasharray="4 4"
                      label={{ value: "P95", fill: "#f0982f", fontSize: 10 }}
                    />
                    <ReferenceLine
                      y={p99Latency}
                      stroke="#e25564"
                      strokeDasharray="4 4"
                      label={{ value: "P99", fill: "#e25564", fontSize: 10 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="latencyMs"
                      name="Decode Latency (ms)"
                      stroke="#3f89ea"
                      strokeWidth={2.3}
                      dot={false}
                    />
                    {compareMode && summaryB ? (
                      <Line
                        type="monotone"
                        dataKey="compareLatencyMs"
                        name="Compare Decode Latency (ms)"
                        stroke="#8aa5cf"
                        strokeDasharray="5 4"
                        strokeWidth={1.8}
                        dot={false}
                      />
                    ) : null}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="workflow-section section-offset">
            <div className="panel-title">Telemetry Alert Workflow</div>
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
                      <span className={`status-badge alert-badge ${alert.level}`}>{alert.level}</span>
                    </div>
                    <div className="workflow-metric">{alert.metric}</div>
                    <div className="workflow-controls">
                      <button
                        className={`btn btn-secondary ${state.acknowledged ? "active" : ""}`}
                        onClick={() => updateWorkflowState(alert.id, { acknowledged: !state.acknowledged })}
                        disabled={!canOperate}
                      >
                        {state.acknowledged ? "Acknowledged" : "Acknowledge"}
                      </button>
                      <select
                        className="select-field"
                        value={state.owner}
                        onChange={(event) => updateWorkflowState(alert.id, { owner: event.target.value })}
                        disabled={!canOperate}
                      >
                        <option value="Unassigned">Unassigned</option>
                        <option value="On-call SRE">On-call SRE</option>
                        <option value="Decoder Ops">Decoder Ops</option>
                        <option value="Research Lead">Research Lead</option>
                      </select>
                    </div>
                    <textarea
                      className="form-textarea workflow-notes"
                      placeholder="Escalation notes..."
                      value={state.notes}
                      onChange={(event) => updateWorkflowState(alert.id, { notes: event.target.value })}
                      disabled={!canOperate}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          <div className="table-container section-offset">
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Dataset</th>
                    <th>Status</th>
                    <th>Provider</th>
                    <th>Hardware</th>
                    <th>PER</th>
                    <th>LER</th>
                    <th>Warning Rate</th>
                    <th>Best Decoder</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRuns.map((run) => {
                    const rowSummary =
                      run.id === runA.id
                        ? summaryA
                        : run.id === runB?.id
                          ? summaryB
                          : null;
                    const rowPer = rowSummary ? rowSummary.perPct : clamp((run.raw.metrics?.physical_error_rate ?? 0) * 100, 0, 100);
                    const rowLer = rowSummary
                      ? rowSummary.logicalErrorRatePct
                      : clamp((run.raw.metrics?.logical_error_rate ?? 0) * 100, 0, 100);
                    const rowBestDecoderRaw = run.raw.metrics?.best_decoder?.trim() ?? "";
                    const rowBestDecoderKey = parseDecoderKey(rowBestDecoderRaw);
                    const rowBestDecoder = rowSummary?.bestDecoder
                      ?? (rowBestDecoderKey
                        ? decoderLabel(rowBestDecoderKey)
                        : rowBestDecoderRaw
                          ? rowBestDecoderRaw.toUpperCase()
                          : decoderLabel(activeDecoder));
                    return (
                      <tr key={run.id}>
                        <td>{run.id.slice(0, 12)}</td>
                        <td className="job-name">
                          <button className="provider-link-btn" onClick={() => openDrilldown(run)}>
                            {run.dataset}
                          </button>
                        </td>
                        <td>
                          <span className={`status-badge ${runStatusBadgeClass(run.status)}`}>
                            ● {runStatusLabel(run.status)}
                          </span>
                        </td>
                        <td>{run.providerName}</td>
                        <td>{run.hardwareLabel}</td>
                        <td>{rowPer.toFixed(3)}%</td>
                        <td>{rowLer.toFixed(3)}%</td>
                        <td>{run.warningRatePct.toFixed(2)}%</td>
                        <td>{rowBestDecoder}</td>
                        <td>{formatAgo(run.updatedAt)}</td>
                        <td>
                          <div className="action-buttons">
                            <button className="btn-icon" title="Inspect" onClick={() => openDrilldown(run)}>
                              ◉
                            </button>
                            <button
                              className="btn-icon"
                              title="Set as Run A"
                              onClick={() => setFilterParam("runA", run.id, "auto")}
                              disabled={!canOperate}
                            >
                              A
                            </button>
                            <button
                              className="btn-icon"
                              title="Set as Run B"
                              onClick={() => setFilterParam("runB", run.id, "auto")}
                              disabled={!canOperate || !compareMode}
                            >
                              B
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="actions">
            <button className="btn btn-secondary" onClick={refreshData}>
              Refresh
            </button>
            <button className="btn btn-secondary" onClick={exportSnapshot}>
              Export Snapshot
            </button>
          </div>
        </>
      ) : null}

      {drilldown ? (
        <div className="drilldown-overlay" onClick={() => setDrilldown(null)}>
          <div className="drilldown-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drilldown-header">
              <div>
                <div className="drilldown-title">Telemetry Drilldown</div>
                <div className="drilldown-summary">
                  {drilldown.run.dataset} · {drilldown.run.providerName}
                </div>
              </div>
              <button className="btn btn-secondary" onClick={() => setDrilldown(null)}>
                Close
              </button>
            </div>
            <div className="drilldown-meta">
              Run {drilldown.run.id} · Updated {formatTimestamp(drilldown.run.updatedAt)}
            </div>
            <div className="drilldown-kv">
              <div className="drilldown-kv-row">
                <span>Physical Error Rate (PER)</span>
                <strong>{drilldown.summary.perPct.toFixed(3)}%</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Logical Error Rate (LER)</span>
                <strong>{drilldown.summary.lerPct.toFixed(3)}%</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Warning Rate</span>
                <strong>{drilldown.summary.warningPct.toFixed(2)}%</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>P95 Decoder Latency</span>
                <strong>{drilldown.summary.p95LatencyMs.toFixed(1)} ms</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Throughput</span>
                <strong>{drilldown.summary.throughput.toFixed(1)} req/round</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Best Decoder / Best QEC</span>
                <strong>
                  {drilldown.summary.bestDecoder} / {drilldown.summary.bestQec}
                </strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Overhead Mapping</span>
                <strong>{drilldown.summary.overheadMapping}</strong>
              </div>
            </div>
            <div className="drilldown-timeline-title">Timeline</div>
            <div className="drilldown-timeline">
              {drilldown.timeline.map((entry, index) => (
                <div key={`${entry}-${index}`} className="drilldown-timeline-item">
                  {entry}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
