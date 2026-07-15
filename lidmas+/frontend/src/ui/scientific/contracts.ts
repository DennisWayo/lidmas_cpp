export type ScientificState =
  | "IDLE"
  | "INGESTING"
  | "PARTIAL"
  | "EXACT"
  | "VALIDATED"
  | "DEGRADED";

export type ScientificField =
  | "logical_failures"
  | "logical_trials"
  | "physical_error_events"
  | "physical_error_opportunities"
  | "request_line_count"
  | "response_line_count"
  | "rounds"
  | "stabilizer_count"
  | "syndrome_opportunities"
  | "residual_syndrome_events"
  | "expanded_shot_count";

export type ScientificCardKey =
  | "ler"
  | "per"
  | "response_ratio"
  | "rounds"
  | "stabilizer_count"
  | "syndrome_opportunities"
  | "post_correction_overhead"
  | "residual_syndrome_rate"
  | "request_line_count"
  | "response_line_count"
  | "expanded_shot_count";

export interface ScientificCardContract {
  key: ScientificCardKey;
  label: string;
  requiredFields: ScientificField[];
  exactness: "exact";
  stateEligibility: ScientificState[];
}

export interface ScientificMetricAvailability {
  contractKey: ScientificCardKey;
  available: boolean;
  missingFields: ScientificField[];
  availabilityReason: string;
}

export interface ScientificIntegrityIssue {
  code: string;
  message: string;
  fields: ScientificField[];
  blocking: boolean;
}

export interface ScientificCompleteness {
  percentage: number;
  availableSignals: ScientificField[];
  missingSignals: ScientificField[];
  impactSummary: string[];
}

export const SCIENTIFIC_FIELD_LABELS: Record<ScientificField, string> = {
  logical_failures: "logical_failures",
  logical_trials: "logical_trials",
  physical_error_events: "physical_error_events",
  physical_error_opportunities: "physical_error_opportunities",
  request_line_count: "request_line_count",
  response_line_count: "response_line_count",
  rounds: "rounds",
  stabilizer_count: "stabilizer_count",
  syndrome_opportunities: "syndrome_opportunities",
  residual_syndrome_events: "residual_syndrome_events",
  expanded_shot_count: "expanded_shot_count",
};

export const SCIENTIFIC_CARD_CONTRACTS: Record<ScientificCardKey, ScientificCardContract> = {
  ler: {
    key: "ler",
    label: "Active Decoder LER",
    requiredFields: ["logical_failures", "logical_trials"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  per: {
    key: "per",
    label: "Physical Error Rate (PER)",
    requiredFields: ["physical_error_events", "physical_error_opportunities"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  response_ratio: {
    key: "response_ratio",
    label: "Decoder Response Ratio",
    requiredFields: ["request_line_count", "response_line_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  rounds: {
    key: "rounds",
    label: "Rounds",
    requiredFields: ["rounds"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  stabilizer_count: {
    key: "stabilizer_count",
    label: "Stabilizer Count",
    requiredFields: ["stabilizer_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  syndrome_opportunities: {
    key: "syndrome_opportunities",
    label: "Syndrome Opportunities",
    requiredFields: ["syndrome_opportunities"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  post_correction_overhead: {
    key: "post_correction_overhead",
    label: "Overhead Mapping",
    requiredFields: ["rounds", "stabilizer_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  residual_syndrome_rate: {
    key: "residual_syndrome_rate",
    label: "Residual Syndrome Rate",
    requiredFields: ["residual_syndrome_events", "syndrome_opportunities"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  request_line_count: {
    key: "request_line_count",
    label: "Request Lines",
    requiredFields: ["request_line_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  response_line_count: {
    key: "response_line_count",
    label: "Response Lines",
    requiredFields: ["response_line_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
  expanded_shot_count: {
    key: "expanded_shot_count",
    label: "Expanded Shot Count",
    requiredFields: ["expanded_shot_count"],
    exactness: "exact",
    stateEligibility: ["PARTIAL", "EXACT", "VALIDATED"],
  },
};

export const SCIENTIFIC_PRIMARY_CARD_ORDER: ScientificCardKey[] = [
  "ler",
  "per",
  "response_ratio",
  "rounds",
  "stabilizer_count",
  "syndrome_opportunities",
];

export const SCIENTIFIC_SECONDARY_CARD_ORDER: ScientificCardKey[] = [
  "request_line_count",
  "response_line_count",
  "post_correction_overhead",
  "residual_syndrome_rate",
  "expanded_shot_count",
];

export const SCIENTIFIC_REQUIRED_CONTRACT_KEYS: ScientificCardKey[] = [
  "ler",
  "per",
  "response_ratio",
  "rounds",
  "stabilizer_count",
  "syndrome_opportunities",
  "residual_syndrome_rate",
];
