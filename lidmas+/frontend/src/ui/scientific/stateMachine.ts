import type { Run, RunTelemetry } from "../../api/types";
import { decoderMatchesKey, type DecoderKey } from "../../data/decoders";
import {
  SCIENTIFIC_CARD_CONTRACTS,
  SCIENTIFIC_REQUIRED_CONTRACT_KEYS,
  SCIENTIFIC_FIELD_LABELS,
  type ScientificCardContract,
  type ScientificCardKey,
  type ScientificCompleteness,
  type ScientificField,
  type ScientificIntegrityIssue,
  type ScientificMetricAvailability,
  type ScientificState,
} from "./contracts";

const EPSILON = 1e-9;

export interface ScientificSignals {
  logical_failures: number | null;
  logical_trials: number | null;
  physical_error_events: number | null;
  physical_error_opportunities: number | null;
  request_line_count: number | null;
  response_line_count: number | null;
  rounds: number | null;
  stabilizer_count: number | null;
  syndrome_opportunities: number | null;
  residual_syndrome_events: number | null;
  expanded_shot_count: number | null;
  request_count: number | null;
  response_ratio_reported: number | null;
}

export interface ResolveScientificStateInput {
  run: Run | null;
  telemetry: RunTelemetry | null;
  activeDecoder: DecoderKey;
  validationPassed?: boolean;
}

export interface ScientificStateResult {
  state: ScientificState;
  completeness: ScientificCompleteness;
  integrityIssues: ScientificIntegrityIssue[];
  signals: ScientificSignals;
  metricAvailability: Record<ScientificCardKey, ScientificMetricAvailability>;
  hasRunContext: boolean;
  hasTelemetryContext: boolean;
}

function asCount(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return Math.trunc(value);
}

function decoderAlias(value: string | null | undefined): DecoderKey | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes("neural")) {
    return "neural_mwpm";
  }
  if (normalized.includes("union_find") || normalized.includes("union-find")) {
    return "uf";
  }
  if (normalized === "uf" || normalized.startsWith("uf_")) {
    return "uf";
  }
  if (normalized === "bp" || normalized.startsWith("bp_") || normalized.includes("belief")) {
    return "bp";
  }
  if (normalized.includes("mwpm")) {
    return "mwpm";
  }
  return null;
}

export function decoderRowMatchesActive(decoderName: string | null | undefined, activeDecoder: DecoderKey): boolean {
  if (!decoderName) {
    return false;
  }
  if (decoderMatchesKey(decoderName, activeDecoder)) {
    return true;
  }
  return decoderAlias(decoderName) === activeDecoder;
}

function signalLabels(fields: ScientificField[]): string {
  return fields.map((field) => SCIENTIFIC_FIELD_LABELS[field]).join(", ");
}

function availabilityReasonForMissingFields(
  contract: ScientificCardContract,
  missing: ScientificField[],
  hasRun: boolean,
  hasTelemetry: boolean,
): string {
  if (!hasRun && !hasTelemetry) {
    return "No active scientific context";
  }
  if (!hasTelemetry) {
    return "Awaiting scientific telemetry";
  }
  if (contract.key === "ler") {
    return "Awaiting decoder output: logical_failures/logical_trials missing";
  }
  if (contract.key === "per") {
    if (missing.includes("physical_error_events")) {
      return "Physical error events not provided by adapter";
    }
    return "Missing physical_error_opportunities";
  }
  if (contract.key === "response_ratio") {
    if (missing.includes("request_line_count")) {
      return "Missing request_line_count";
    }
    return "Missing response_line_count";
  }
  if (contract.key === "rounds") {
    return "Missing rounds";
  }
  if (contract.key === "stabilizer_count") {
    return "Missing stabilizer_count";
  }
  if (contract.key === "syndrome_opportunities") {
    return "Missing syndrome_opportunities";
  }
  if (contract.key === "post_correction_overhead") {
    return "Awaiting rounds and stabilizer_count for overhead mapping";
  }
  if (contract.key === "residual_syndrome_rate") {
    if (missing.includes("residual_syndrome_events")) {
      return "Residual syndrome events not provided by adapter";
    }
    return "Missing syndrome_opportunities";
  }
  if (contract.key === "request_line_count") {
    return "Missing request_line_count";
  }
  if (contract.key === "response_line_count") {
    return "Missing response_line_count";
  }
  if (contract.key === "expanded_shot_count") {
    return "Expanded shot count not provided by adapter";
  }
  return `Missing ${signalLabels(missing)}`;
}

export function evaluateScientificMetricAvailability(
  contract: ScientificCardContract,
  signals: ScientificSignals,
  hasRun: boolean,
  hasTelemetry: boolean,
): ScientificMetricAvailability {
  const missingFields = contract.requiredFields.filter((field) => signals[field] == null);
  if (missingFields.length === 0) {
    if (
      contract.key === "ler" &&
      signals.logical_failures != null &&
      signals.logical_trials != null
    ) {
      if (signals.logical_trials <= 0) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "logical_trials must be greater than zero",
        };
      }
      if (signals.logical_failures > signals.logical_trials) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "logical_failures exceeds logical_trials",
        };
      }
    }
    if (
      contract.key === "per" &&
      signals.physical_error_events != null &&
      signals.physical_error_opportunities != null
    ) {
      if (signals.physical_error_opportunities <= 0) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "physical_error_opportunities must be greater than zero",
        };
      }
      if (signals.physical_error_events > signals.physical_error_opportunities) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "physical_error_events exceeds physical_error_opportunities",
        };
      }
    }
    if (
      contract.key === "response_ratio" &&
      signals.request_line_count != null &&
      signals.request_line_count <= 0
    ) {
      return {
        contractKey: contract.key,
        available: false,
        missingFields: [],
        availabilityReason: "request_line_count must be greater than zero",
      };
    }
    if (
      contract.key === "residual_syndrome_rate" &&
      signals.residual_syndrome_events != null &&
      signals.syndrome_opportunities != null
    ) {
      if (signals.syndrome_opportunities <= 0) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "syndrome_opportunities must be greater than zero",
        };
      }
      if (signals.residual_syndrome_events > signals.syndrome_opportunities) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "residual_syndrome_events exceeds syndrome_opportunities",
        };
      }
    }
    if (contract.key === "post_correction_overhead") {
      if (signals.rounds != null && signals.rounds <= 0) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "rounds must be greater than zero",
        };
      }
      if (signals.stabilizer_count != null && signals.stabilizer_count <= 0) {
        return {
          contractKey: contract.key,
          available: false,
          missingFields: [],
          availabilityReason: "stabilizer_count must be greater than zero",
        };
      }
    }
    return {
      contractKey: contract.key,
      available: true,
      missingFields: [],
      availabilityReason: "Exact scientific contract satisfied",
    };
  }
  return {
    contractKey: contract.key,
    available: false,
    missingFields,
    availabilityReason: availabilityReasonForMissingFields(contract, missingFields, hasRun, hasTelemetry),
  };
}

function collectSignals(run: Run | null, telemetry: RunTelemetry | null, activeDecoder: DecoderKey): ScientificSignals {
  const runMetrics = run?.metrics ?? null;
  if (!telemetry && !runMetrics) {
    return {
      logical_failures: null,
      logical_trials: null,
      physical_error_events: null,
      physical_error_opportunities: null,
      request_line_count: null,
      response_line_count: null,
      rounds: null,
      stabilizer_count: null,
      syndrome_opportunities: null,
      residual_syndrome_events: null,
      expanded_shot_count: null,
      request_count: null,
      response_ratio_reported: null,
    };
  }

  const telemetryExactRows = telemetry?.decoder_exact_metrics ?? [];
  const runExactRows = runMetrics?.decoder_exact_metrics ?? [];
  const exactRows = telemetryExactRows.length > 0 ? telemetryExactRows : runExactRows;
  const activeExact = exactRows.find(
    (entry) =>
      decoderRowMatchesActive(entry.decoder, activeDecoder) &&
      entry.trials > 0 &&
      entry.logical_failures >= 0 &&
      entry.logical_failures <= entry.trials,
  );

  const telemetryMatchesActiveDecoder = telemetry?.decoder_name
    ? decoderRowMatchesActive(telemetry.decoder_name, activeDecoder)
    : false;
  const runMatchesActiveDecoder = runMetrics?.best_decoder
    ? decoderRowMatchesActive(runMetrics.best_decoder, activeDecoder)
    : false;

  const logicalFailures = activeExact
    ? asCount(activeExact.logical_failures)
    : telemetryMatchesActiveDecoder
      ? asCount(telemetry?.logical_failures)
      : runMatchesActiveDecoder
        ? asCount(runMetrics?.logical_failures)
        : null;
  const logicalTrials = activeExact
    ? asCount(activeExact.trials)
    : telemetryMatchesActiveDecoder
      ? asCount(telemetry?.logical_trials)
      : runMatchesActiveDecoder
        ? asCount(runMetrics?.logical_trials)
        : null;
  const rounds = asCount(telemetry?.rounds ?? runMetrics?.rounds);
  const stabilizerCount = asCount(telemetry?.stabilizer_count ?? runMetrics?.stabilizer_count);
  const explicitSyndromeOpportunities = asCount(
    telemetry?.syndrome_opportunities ?? runMetrics?.syndrome_opportunities,
  );
  // If the backend does not provide syndrome_opportunities directly, derive from exact run-level dimensions.
  const syndromeOpportunities =
    explicitSyndromeOpportunities ??
    (rounds != null && stabilizerCount != null ? rounds * stabilizerCount : null);

  const requestLineCount = asCount(telemetry?.request_line_count ?? runMetrics?.request_line_count);
  const responseLineCount = asCount(telemetry?.response_line_count ?? runMetrics?.response_line_count);
  const responseRatioReported =
    telemetry?.response_ratio != null && Number.isFinite(telemetry.response_ratio)
      ? telemetry.response_ratio
      : null;

  return {
    logical_failures: logicalFailures,
    logical_trials: logicalTrials,
    physical_error_events: asCount(telemetry?.physical_error_events ?? runMetrics?.physical_error_events),
    physical_error_opportunities: asCount(
      telemetry?.physical_error_opportunities ?? runMetrics?.physical_error_opportunities,
    ),
    request_line_count: requestLineCount,
    response_line_count: responseLineCount,
    rounds,
    stabilizer_count: stabilizerCount,
    syndrome_opportunities: syndromeOpportunities,
    residual_syndrome_events: asCount(
      telemetry?.residual_syndrome_events ?? runMetrics?.residual_syndrome_events,
    ),
    expanded_shot_count: asCount(telemetry?.expanded_shot_count ?? runMetrics?.expanded_shot_count),
    request_count: asCount(telemetry?.request_count),
    response_ratio_reported: responseRatioReported,
  };
}

function runProvidesScientificSignals(run: Run | null): boolean {
  const metrics = run?.metrics;
  if (!metrics) {
    return false;
  }
  return (
    metrics.logical_failures != null ||
    metrics.logical_trials != null ||
    metrics.physical_error_events != null ||
    metrics.physical_error_opportunities != null ||
    metrics.request_line_count != null ||
    metrics.response_line_count != null ||
    metrics.rounds != null ||
    metrics.stabilizer_count != null ||
    metrics.syndrome_opportunities != null ||
    metrics.residual_syndrome_events != null ||
    metrics.expanded_shot_count != null ||
    (metrics.decoder_exact_metrics?.length ?? 0) > 0
  );
}

function integrityIssuesForSignals(signals: ScientificSignals): ScientificIntegrityIssue[] {
  const issues: ScientificIntegrityIssue[] = [];

  if (
    signals.logical_failures != null &&
    signals.logical_trials != null &&
    signals.logical_failures > signals.logical_trials
  ) {
    issues.push({
      code: "logical_denominator_conflict",
      message: "logical_failures exceeds logical_trials",
      fields: ["logical_failures", "logical_trials"],
      blocking: true,
    });
  }

  if (
    signals.physical_error_events != null &&
    signals.physical_error_opportunities != null &&
    signals.physical_error_opportunities <= 0
  ) {
    issues.push({
      code: "physical_denominator_non_positive",
      message: "physical_error_opportunities must be greater than zero",
      fields: ["physical_error_opportunities"],
      blocking: true,
    });
  }

  if (
    signals.physical_error_events != null &&
    signals.physical_error_opportunities != null &&
    signals.physical_error_events > signals.physical_error_opportunities
  ) {
    issues.push({
      code: "physical_denominator_conflict",
      message: "physical_error_events exceeds physical_error_opportunities",
      fields: ["physical_error_events", "physical_error_opportunities"],
      blocking: true,
    });
  }

  if (
    signals.residual_syndrome_events != null &&
    signals.syndrome_opportunities != null &&
    signals.syndrome_opportunities <= 0
  ) {
    issues.push({
      code: "residual_denominator_non_positive",
      message: "syndrome_opportunities must be greater than zero for residual_syndrome_rate",
      fields: ["syndrome_opportunities"],
      blocking: true,
    });
  }

  if (
    signals.residual_syndrome_events != null &&
    signals.syndrome_opportunities != null &&
    signals.residual_syndrome_events > signals.syndrome_opportunities
  ) {
    issues.push({
      code: "residual_denominator_conflict",
      message: "residual_syndrome_events exceeds syndrome_opportunities",
      fields: ["residual_syndrome_events", "syndrome_opportunities"],
      blocking: true,
    });
  }

  if (
    signals.rounds != null &&
    signals.stabilizer_count != null &&
    signals.syndrome_opportunities != null &&
    signals.syndrome_opportunities !== signals.rounds * signals.stabilizer_count
  ) {
    issues.push({
      code: "syndrome_denominator_conflict",
      message: "syndrome_opportunities conflicts with rounds * stabilizer_count",
      fields: ["rounds", "stabilizer_count", "syndrome_opportunities"],
      blocking: true,
    });
  }

  if (
    signals.request_count != null &&
    signals.request_line_count != null &&
    signals.request_count < signals.request_line_count
  ) {
    issues.push({
      code: "request_count_scope_conflict",
      message: "request_count is lower than request_line_count and conflicts with expanded-shot semantics",
      fields: ["request_line_count"],
      blocking: true,
    });
  }

  if (
    signals.request_line_count != null &&
    signals.response_line_count != null &&
    signals.request_line_count <= 0 &&
    signals.response_line_count > 0
  ) {
    issues.push({
      code: "response_ratio_denominator_non_positive",
      message: "request_line_count must be greater than zero when response_line_count is present",
      fields: ["request_line_count", "response_line_count"],
      blocking: true,
    });
  }

  if (
    signals.response_ratio_reported != null &&
    signals.request_line_count != null &&
    signals.response_line_count != null &&
    signals.request_line_count > 0
  ) {
    const derivedRatio = signals.response_line_count / signals.request_line_count;
    if (Math.abs(signals.response_ratio_reported - derivedRatio) > EPSILON) {
      issues.push({
        code: "response_ratio_conflict",
        message: "response_ratio conflicts with response_line_count/request_line_count",
        fields: ["response_line_count", "request_line_count"],
        blocking: true,
      });
    }
  }

  return issues;
}

function computeCompleteness(
  availabilityMap: Record<ScientificCardKey, ScientificMetricAvailability>,
): ScientificCompleteness {
  const requiredFields = Array.from(
    new Set(
      SCIENTIFIC_REQUIRED_CONTRACT_KEYS.flatMap(
        (key) => SCIENTIFIC_CARD_CONTRACTS[key].requiredFields,
      ),
    ),
  );

  const unavailableRequiredContracts = SCIENTIFIC_REQUIRED_CONTRACT_KEYS.filter(
    (key) => !availabilityMap[key].available,
  );
  const missingSignals = Array.from(
    new Set(
      unavailableRequiredContracts.flatMap((key) => {
        const availability = availabilityMap[key];
        if (availability.missingFields.length > 0) {
          return availability.missingFields;
        }
        return SCIENTIFIC_CARD_CONTRACTS[key].requiredFields;
      }),
    ),
  );
  const availableSignals = requiredFields.filter((field) => !missingSignals.includes(field));
  const percentage = Math.round((availableSignals.length / Math.max(1, requiredFields.length)) * 100);

  const impactSummary = SCIENTIFIC_REQUIRED_CONTRACT_KEYS.map((key) => {
    const contract = SCIENTIFIC_CARD_CONTRACTS[key];
    const availability = availabilityMap[key];
    if (availability.available) {
      return `${contract.label}: exact`;
    }
    return `${contract.label}: ${availability.availabilityReason}`;
  });

  return {
    percentage,
    availableSignals,
    missingSignals,
    impactSummary,
  };
}

function scientificStateFromContext(
  hasRun: boolean,
  hasTelemetry: boolean,
  issues: ScientificIntegrityIssue[],
  availableRequiredContracts: number,
  requiredContractCount: number,
  validationPassed: boolean,
): ScientificState {
  if (!hasRun && !hasTelemetry) {
    return "IDLE";
  }

  if (issues.some((issue) => issue.blocking)) {
    return "DEGRADED";
  }

  if (!hasTelemetry || availableRequiredContracts === 0) {
    return "INGESTING";
  }

  if (availableRequiredContracts < requiredContractCount) {
    return "PARTIAL";
  }

  return validationPassed ? "VALIDATED" : "EXACT";
}

export function resolveScientificState(input: ResolveScientificStateInput): ScientificStateResult {
  const hasRunContext = Boolean(input.run);
  const hasTelemetryContext = Boolean(input.telemetry) || runProvidesScientificSignals(input.run);
  const signals = collectSignals(input.run, input.telemetry, input.activeDecoder);
  const validationPassed =
    input.validationPassed ?? Boolean(input.run?.metrics?.scientific_validation_ready);

  const availabilityEntries = Object.values(SCIENTIFIC_CARD_CONTRACTS).map((contract) => [
    contract.key,
    evaluateScientificMetricAvailability(
      contract,
      signals,
      hasRunContext,
      hasTelemetryContext,
    ),
  ]);
  const metricAvailability = Object.fromEntries(availabilityEntries) as Record<
    ScientificCardKey,
    ScientificMetricAvailability
  >;

  const integrityIssues = integrityIssuesForSignals(signals);
  const completeness = computeCompleteness(metricAvailability);
  const availableRequiredContracts = SCIENTIFIC_REQUIRED_CONTRACT_KEYS.filter(
    (key) => metricAvailability[key].available,
  ).length;
  const requiredContractCount = SCIENTIFIC_REQUIRED_CONTRACT_KEYS.length;

  const state = scientificStateFromContext(
    hasRunContext,
    hasTelemetryContext,
    integrityIssues,
    availableRequiredContracts,
    requiredContractCount,
    validationPassed,
  );

  return {
    state,
    completeness,
    integrityIssues,
    signals,
    metricAvailability,
    hasRunContext,
    hasTelemetryContext,
  };
}

export function scientificStateLabel(state: ScientificState): string {
  if (state === "IDLE") {
    return "No Scientific Context";
  }
  if (state === "INGESTING") {
    return "Ingesting Scientific Evidence";
  }
  if (state === "PARTIAL") {
    return "Partial Exactness";
  }
  if (state === "EXACT") {
    return "Exact Scientific Metrics";
  }
  if (state === "VALIDATED") {
    return "Scientific Validation Passed";
  }
  return "Scientific Integrity Compromised";
}

export function scientificStateStatusClass(state: ScientificState): string {
  if (state === "IDLE") {
    return "status-warning";
  }
  if (state === "INGESTING") {
    return "status-running";
  }
  if (state === "PARTIAL") {
    return "status-warning";
  }
  if (state === "EXACT") {
    return "status-success";
  }
  if (state === "VALIDATED") {
    return "status-success";
  }
  return "status-failed";
}
