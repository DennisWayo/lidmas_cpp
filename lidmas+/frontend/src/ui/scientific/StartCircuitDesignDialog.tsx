import { ArrowDown, ArrowUp, Download, Plus, Trash2, Upload } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { apiFetch } from "../../api/client";
import {
  calibrationSnapshotsForContext,
  defaultCalibrationSnapshotId,
  normalizeVendorCalibrationSnapshots,
  type VendorCalibrationSnapshot,
} from "../../data/vendorCalibrations";

type CircuitGate =
  | "h"
  | "x"
  | "y"
  | "z"
  | "s"
  | "t"
  | "rx"
  | "ry"
  | "rz"
  | "cx"
  | "cz"
  | "ms"
  | "disp"
  | "sq"
  | "phase"
  | "bs"
  | "kerr"
  | "cubic"
  | "measure";
export type CircuitHardwareTarget = "superconducting" | "trapped_ion" | "photonic";
export type CircuitProviderFamily =
  | "xanadu"
  | "ankaa"
  | "ibm"
  | "pennylane"
  | "qiskit"
  | "cirq"
  | "unknown";

export interface CircuitOperation {
  id: string;
  gate: CircuitGate;
  target: number;
  control?: number;
  parameter?: number;
}

export interface CircuitDesignDraft {
  name: string;
  qubitCount: number;
  operations: CircuitOperation[];
  qasm: string;
  depth: number;
  gateCount: number;
  hardwareTarget: CircuitHardwareTarget;
  noiseConfig: CircuitNoiseConfig;
  compileArtifact: CircuitCompileArtifact;
  calibrationSnapshotId?: string;
}

interface StartCircuitDesignDialogProps {
  open: boolean;
  pending: boolean;
  providerName: string;
  providerFamily: CircuitProviderFamily;
  onClose: () => void;
  onStart: (draft: CircuitDesignDraft) => void;
}

export type CircuitNoisePreset = "low" | "medium" | "high" | "custom";

export type CircuitNoiseChannelKey =
  | "amplitude_damping"
  | "dephasing"
  | "depolarizing"
  | "readout_error"
  | "crosstalk_zz"
  | "ms_overrotation"
  | "motional_heating"
  | "addressing_crosstalk"
  | "spam_error"
  | "photon_loss"
  | "mode_mismatch"
  | "phase_drift"
  | "detector_dark_count"
  | "non_gaussian_injection_failure";

export interface CircuitNoiseChannelConfig {
  enabled: boolean;
  level: number;
}

export interface CircuitNoiseConfig {
  preset: CircuitNoisePreset;
  channels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>>;
}

type CircuitPreviewCellKind = "wire" | "gate" | "measure" | "control" | "target";

interface CircuitPreviewCellModel {
  kind: CircuitPreviewCellKind;
  label: string | null;
  hasConnector: boolean;
}

interface GateOption {
  value: CircuitGate;
  label: string;
}

interface NoiseChannelOption {
  key: CircuitNoiseChannelKey;
  label: string;
}

interface MeasurementPreviewRow {
  label: string;
  target: number;
  probabilityZero: number;
  probabilityOne: number;
  intendedBit: 0 | 1;
}

interface MeasurementPreviewModel {
  warning: string;
  modelLabel: string;
  rows: MeasurementPreviewRow[];
  unavailableReason?: string;
}

interface CompileMetricRow {
  label: string;
  value: string;
}

interface CircuitCompileReport {
  profileLabel: string;
  fidelityBand: string;
  warnings: string[];
  metrics: CompileMetricRow[];
}

interface CalibrationScaleFactors {
  oneQubitScale: number;
  twoQubitScale: number;
  measurementScale: number;
  timingScale: number;
  backgroundScale: number;
  zBiasScale: number;
}

type PhotonicDetectorModel = "threshold" | "pnr_approx";

interface CircuitCompiledOperation {
  gate: string;
  target: number;
  control?: number;
  parameter?: number;
  duration_ns: number;
  source_index: number;
}

interface CircuitSyndromePreview {
  rounds_est: number;
  stabilizer_count_est: number;
  x_events_est: number;
  z_events_est: number;
  logical_error_hint: number;
}

export interface CircuitCompileArtifact {
  schema_version: "v1";
  hardware_target: CircuitHardwareTarget;
  provider_family: CircuitProviderFamily;
  calibration_snapshot_id: string;
  calibration_vendor: string;
  calibration_backend: string;
  calibration_captured_at: string;
  calibration_source: string;
  native_basis: string[];
  coupling_map: Array<[number, number]>;
  photonic_detector_model: PhotonicDetectorModel;
  source_depth: number;
  transpiled_depth: number;
  source_gate_count: number;
  transpiled_gate_count: number;
  swap_insertions: number;
  schedule_conflicts: number;
  total_duration_ns: number;
  warnings: string[];
  syndrome_preview: CircuitSyndromePreview;
  transpiled_operations: CircuitCompiledOperation[];
}

interface ComplexValue {
  re: number;
  im: number;
}

interface ComplexMatrix2 {
  m00: ComplexValue;
  m01: ComplexValue;
  m10: ComplexValue;
  m11: ComplexValue;
}

interface QubitBranchState {
  weight: number;
  re: Float64Array;
  im: Float64Array;
}

interface PhotonicBranchState {
  weight: number;
  amplitude: Float64Array;
  phase: Float64Array;
}

const SUPERCONDUCTING_GATE_OPTIONS: GateOption[] = [
  { value: "h", label: "H" },
  { value: "x", label: "X" },
  { value: "y", label: "Y" },
  { value: "z", label: "Z" },
  { value: "s", label: "S" },
  { value: "t", label: "T" },
  { value: "rx", label: "RX" },
  { value: "ry", label: "RY" },
  { value: "rz", label: "RZ" },
  { value: "cx", label: "CX" },
  { value: "cz", label: "CZ" },
  { value: "measure", label: "MEASURE" },
];

const TRAPPED_ION_GATE_OPTIONS: GateOption[] = [
  { value: "x", label: "X" },
  { value: "y", label: "Y" },
  { value: "z", label: "Z" },
  { value: "rx", label: "RX" },
  { value: "ry", label: "RY" },
  { value: "rz", label: "RZ" },
  { value: "ms", label: "MS" },
  { value: "measure", label: "MEASURE" },
];

const PHOTONIC_GATE_OPTIONS: GateOption[] = [
  { value: "disp", label: "DISP (Gaussian)" },
  { value: "sq", label: "SQ (Gaussian)" },
  { value: "phase", label: "PHASE (Gaussian)" },
  { value: "bs", label: "BS (Gaussian)" },
  { value: "kerr", label: "KERR (Non-Gaussian)" },
  { value: "cubic", label: "CUBIC (Non-Gaussian)" },
  { value: "measure", label: "MEASURE" },
];

const SUPERCONDUCTING_NOISE_OPTIONS: NoiseChannelOption[] = [
  { key: "amplitude_damping", label: "Amplitude Damping (T1)" },
  { key: "dephasing", label: "Dephasing (T2)" },
  { key: "depolarizing", label: "Gate Depolarizing Error" },
  { key: "readout_error", label: "Readout Assignment Error" },
  { key: "crosstalk_zz", label: "Crosstalk / ZZ Coupling" },
];

const TRAPPED_ION_NOISE_OPTIONS: NoiseChannelOption[] = [
  { key: "dephasing", label: "Laser / Magnetic Dephasing" },
  { key: "ms_overrotation", label: "MS Over/Under-Rotation" },
  { key: "motional_heating", label: "Motional Heating" },
  { key: "addressing_crosstalk", label: "Addressing Crosstalk" },
  { key: "spam_error", label: "SPAM / Readout Error" },
];

const PHOTONIC_NOISE_OPTIONS: NoiseChannelOption[] = [
  { key: "photon_loss", label: "Photon Loss" },
  { key: "mode_mismatch", label: "Mode Mismatch" },
  { key: "phase_drift", label: "Phase Drift" },
  { key: "detector_dark_count", label: "Detector Dark Counts" },
  { key: "non_gaussian_injection_failure", label: "Non-Gaussian Injection Failure" },
];

const PREVIEW_MAX_QUBITS = 10;
const PREVIEW_BRANCH_LIMIT = 128;

function gateNeedsControl(gate: CircuitGate): boolean {
  return gate === "cx" || gate === "cz" || gate === "ms" || gate === "bs";
}

function gateNeedsParameter(gate: CircuitGate): boolean {
  return (
    gate === "rx" ||
    gate === "ry" ||
    gate === "rz" ||
    gate === "ms" ||
    gate === "disp" ||
    gate === "sq" ||
    gate === "phase" ||
    gate === "bs" ||
    gate === "kerr" ||
    gate === "cubic"
  );
}

function gateLabel(gate: CircuitGate): string {
  if (gate === "disp") {
    return "DISP";
  }
  if (gate === "sq") {
    return "SQ";
  }
  if (gate === "phase") {
    return "PHASE";
  }
  if (gate === "bs") {
    return "BS";
  }
  if (gate === "kerr") {
    return "KERR";
  }
  if (gate === "cubic") {
    return "CUBIC";
  }
  return gate.toUpperCase();
}

function formatOperation(operation: CircuitOperation): string {
  const gate = gateLabel(operation.gate);
  if (operation.gate === "measure") {
    return `${gate} q[${operation.target}] -> c[${operation.target}]`;
  }
  if (gateNeedsControl(operation.gate)) {
    return `${gate} q[${operation.control}], q[${operation.target}]`;
  }
  if (gateNeedsParameter(operation.gate)) {
    return `${gate}(${operation.parameter ?? 0}) q[${operation.target}]`;
  }
  return `${gate} q[${operation.target}]`;
}

function buildQasm(qubitCount: number, operations: CircuitOperation[]): string {
  const lines = [
    "OPENQASM 2.0;",
    'include "qelib1.inc";',
    `qreg q[${qubitCount}];`,
    `creg c[${qubitCount}];`,
  ];
  operations.forEach((operation) => {
    if (operation.gate === "measure") {
      lines.push(`measure q[${operation.target}] -> c[${operation.target}];`);
      return;
    }
    if (gateNeedsControl(operation.gate)) {
      if (gateNeedsParameter(operation.gate)) {
        lines.push(
          `${operation.gate}(${operation.parameter ?? 0}) q[${operation.control}],q[${operation.target}];`,
        );
      } else {
        lines.push(`${operation.gate} q[${operation.control}],q[${operation.target}];`);
      }
      return;
    }
    if (gateNeedsParameter(operation.gate)) {
      lines.push(`${operation.gate}(${operation.parameter ?? 0}) q[${operation.target}];`);
      return;
    }
    lines.push(`${operation.gate} q[${operation.target}];`);
  });
  return lines.join("\n");
}

function estimateDepth(qubitCount: number, operations: CircuitOperation[]): number {
  const lastLayerByQubit = Array.from({ length: qubitCount }, () => 0);
  let depth = 0;
  operations.forEach((operation) => {
    if (gateNeedsControl(operation.gate) && operation.control != null) {
      const nextLayer = Math.max(lastLayerByQubit[operation.control], lastLayerByQubit[operation.target]) + 1;
      lastLayerByQubit[operation.control] = nextLayer;
      lastLayerByQubit[operation.target] = nextLayer;
      depth = Math.max(depth, nextLayer);
      return;
    }
    const nextLayer = lastLayerByQubit[operation.target] + 1;
    lastLayerByQubit[operation.target] = nextLayer;
    depth = Math.max(depth, nextLayer);
  });
  return depth;
}

function nextOperationId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function hardwareTargetsForProvider(providerFamily: CircuitProviderFamily): CircuitHardwareTarget[] {
  if (providerFamily === "pennylane") {
    return ["superconducting", "trapped_ion", "photonic"];
  }
  return ["superconducting"];
}

function gateOptionsForHardwareTarget(target: CircuitHardwareTarget): GateOption[] {
  if (target === "photonic") {
    return PHOTONIC_GATE_OPTIONS;
  }
  if (target === "trapped_ion") {
    return TRAPPED_ION_GATE_OPTIONS;
  }
  return SUPERCONDUCTING_GATE_OPTIONS;
}

function noiseOptionsForHardwareTarget(target: CircuitHardwareTarget): NoiseChannelOption[] {
  if (target === "photonic") {
    return PHOTONIC_NOISE_OPTIONS;
  }
  if (target === "trapped_ion") {
    return TRAPPED_ION_NOISE_OPTIONS;
  }
  return SUPERCONDUCTING_NOISE_OPTIONS;
}

function noisePresetLevel(preset: CircuitNoisePreset): number {
  if (preset === "low") {
    return 0.25;
  }
  if (preset === "high") {
    return 0.8;
  }
  return 0.5;
}

function buildNoiseStateFromPreset(
  options: NoiseChannelOption[],
  preset: CircuitNoisePreset,
): Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>> {
  const level = noisePresetLevel(preset);
  const out: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>> = {};
  options.forEach((option) => {
    out[option.key] = { enabled: true, level };
  });
  return out;
}

function hardwareTargetLabel(target: CircuitHardwareTarget): string {
  if (target === "trapped_ion") {
    return "Trapped Ion";
  }
  if (target === "photonic") {
    return "Photonic";
  }
  return "Superconducting";
}

function calibrationScaleFactors(
  hardwareTarget: CircuitHardwareTarget,
  calibrationSnapshot: VendorCalibrationSnapshot | null,
): CalibrationScaleFactors {
  if (!calibrationSnapshot) {
    return {
      oneQubitScale: 1.0,
      twoQubitScale: 1.0,
      measurementScale: 1.0,
      timingScale: 1.0,
      backgroundScale: 1.0,
      zBiasScale: 1.0,
    };
  }

  const metrics = calibrationSnapshot.metrics;
  if (hardwareTarget === "superconducting") {
    const oneQ = metrics.avg_1q_gate_error ?? 0.001;
    const twoQ = metrics.avg_2q_gate_error ?? 0.012;
    const readout = metrics.avg_readout_error ?? 0.022;
    const t1 = metrics.avg_t1_us ?? 80;
    const t2 = metrics.avg_t2_us ?? 70;
    const zz = metrics.zz_coupling_khz ?? 18;
    return {
      oneQubitScale: clamp(0.75 + (oneQ / 0.0012) * 0.25, 0.65, 2.2),
      twoQubitScale: clamp(0.6 + (twoQ / 0.012) * 0.85, 0.65, 2.3),
      measurementScale: clamp(0.5 + (readout / 0.022) * 0.95, 0.6, 2.3),
      timingScale: clamp(0.88 + (100 / Math.max(t1, 1)) * 0.06 + (90 / Math.max(t2, 1)) * 0.06, 0.8, 1.25),
      backgroundScale: clamp((82 / Math.max(t1, 1)) * 0.55 + (72 / Math.max(t2, 1)) * 0.45, 0.55, 2.3),
      zBiasScale: clamp(0.85 + zz / 36, 0.8, 2.3),
    };
  }

  if (hardwareTarget === "trapped_ion") {
    const oneQ = metrics.avg_1q_gate_error ?? 0.0004;
    const ms = metrics.avg_ms_gate_error ?? 0.0035;
    const readout = metrics.avg_readout_error ?? 0.012;
    const coherenceMs = metrics.avg_coherence_ms ?? 700;
    const heating = metrics.heating_quanta_per_ms ?? 0.08;
    const addressing = metrics.addressing_crosstalk ?? 0.018;
    return {
      oneQubitScale: clamp(0.7 + (oneQ / 0.00045) * 0.35, 0.6, 2.0),
      twoQubitScale: clamp(0.65 + (ms / 0.004) * 0.8, 0.65, 2.2),
      measurementScale: clamp(0.55 + (readout / 0.013) * 0.9, 0.6, 2.2),
      timingScale: clamp(0.82 + (800 / Math.max(coherenceMs, 1)) * 0.08, 0.78, 1.2),
      backgroundScale: clamp(0.62 + (heating / 0.09) * 0.65 + (700 / Math.max(coherenceMs, 1)) * 0.2, 0.55, 2.1),
      zBiasScale: clamp(0.9 + (addressing / 0.03) * 0.55, 0.85, 2.0),
    };
  }

  const loss = metrics.photon_loss_rate ?? 0.05;
  const mismatch = metrics.mode_mismatch ?? 0.02;
  const phase = metrics.phase_drift_deg ?? 2.5;
  const dark = metrics.detector_dark_count_rate ?? 0.007;
  const efficiency = metrics.homodyne_efficiency ?? 0.93;
  const nonGaussianFailure = metrics.non_gaussian_injection_failure ?? 0.035;
  return {
    oneQubitScale: clamp(0.75 + (mismatch / 0.025) * 0.75, 0.65, 2.4),
    twoQubitScale: clamp(0.8 + (nonGaussianFailure / 0.04) * 0.8 + (loss / 0.06) * 0.35, 0.7, 2.6),
    measurementScale: clamp(0.6 + (dark / 0.008) * 0.8 + ((1 - efficiency) / 0.08) * 0.7, 0.65, 2.7),
    timingScale: clamp(0.9 + (loss / 0.06) * 0.18 + ((1 - efficiency) / 0.08) * 0.12, 0.85, 1.32),
    backgroundScale: clamp(0.85 + (loss / 0.06) * 0.8 + (phase / 3.2) * 0.42, 0.75, 2.8),
    zBiasScale: clamp(0.9 + (phase / 3.0) * 0.7, 0.85, 2.5),
  };
}

function formatPreviewParameter(value: number | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "0.00";
  }
  return value.toFixed(2);
}

interface CircuitPreviewExportModel {
  circuitName: string;
  providerFamily: CircuitProviderFamily;
  hardwareTarget: CircuitHardwareTarget;
  qubitCount: number;
  operations: CircuitOperation[];
  noisePreset: CircuitNoisePreset;
  noiseChannels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>>;
  photonicDetectorModel: PhotonicDetectorModel;
  calibrationSnapshotId?: string;
}

interface CircuitPreviewPngMetadata {
  schema_version: "v1";
  circuit_name: string;
  provider_family: CircuitProviderFamily;
  hardware_target: CircuitHardwareTarget;
  qubit_count: number;
  operations: Array<{
    gate: CircuitGate;
    target: number;
    control?: number;
    parameter?: number;
  }>;
  noise_config: CircuitNoiseConfig;
  photonic_detector_model: PhotonicDetectorModel;
  calibration_snapshot_id?: string;
  exported_at: string;
}

function sanitizeFileStem(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_");
  const trimmed = normalized.replace(/^_+|_+$/g, "");
  return trimmed || "custom_design";
}

const CIRCUIT_PNG_METADATA_KEYWORD = "lidmas_circuit_v1";
const PNG_SIGNATURE_BYTES = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
const PNG_TEXT_CHUNK_TYPE_BYTES = new Uint8Array([116, 69, 88, 116]);
const UTF8_ENCODER = new TextEncoder();
const UTF8_DECODER = new TextDecoder();

const CIRCUIT_GATE_VALUES: CircuitGate[] = [
  "h",
  "x",
  "y",
  "z",
  "s",
  "t",
  "rx",
  "ry",
  "rz",
  "cx",
  "cz",
  "ms",
  "disp",
  "sq",
  "phase",
  "bs",
  "kerr",
  "cubic",
  "measure",
];
const HARDWARE_TARGET_VALUES: CircuitHardwareTarget[] = ["superconducting", "trapped_ion", "photonic"];
const PROVIDER_FAMILY_VALUES: CircuitProviderFamily[] = ["xanadu", "ankaa", "ibm", "pennylane", "qiskit", "cirq", "unknown"];
const NOISE_PRESET_VALUES: CircuitNoisePreset[] = ["low", "medium", "high", "custom"];
const PHOTONIC_DETECTOR_MODEL_VALUES: PhotonicDetectorModel[] = ["threshold", "pnr_approx"];
const NOISE_CHANNEL_KEY_VALUES: CircuitNoiseChannelKey[] = [
  "amplitude_damping",
  "dephasing",
  "depolarizing",
  "readout_error",
  "crosstalk_zz",
  "ms_overrotation",
  "motional_heating",
  "addressing_crosstalk",
  "spam_error",
  "photon_loss",
  "mode_mismatch",
  "phase_drift",
  "detector_dark_count",
  "non_gaussian_injection_failure",
];

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let value = n;
    for (let bit = 0; bit < 8; bit += 1) {
      if ((value & 1) === 1) {
        value = 0xedb88320 ^ (value >>> 1);
      } else {
        value >>>= 1;
      }
    }
    table[n] = value >>> 0;
  }
  return table;
})();

function isCircuitGate(value: unknown): value is CircuitGate {
  return typeof value === "string" && (CIRCUIT_GATE_VALUES as readonly string[]).includes(value);
}

function isCircuitHardwareTarget(value: unknown): value is CircuitHardwareTarget {
  return typeof value === "string" && (HARDWARE_TARGET_VALUES as readonly string[]).includes(value);
}

function isCircuitProviderFamily(value: unknown): value is CircuitProviderFamily {
  return typeof value === "string" && (PROVIDER_FAMILY_VALUES as readonly string[]).includes(value);
}

function isNoisePreset(value: unknown): value is CircuitNoisePreset {
  return typeof value === "string" && (NOISE_PRESET_VALUES as readonly string[]).includes(value);
}

function isPhotonicDetectorModel(value: unknown): value is PhotonicDetectorModel {
  return typeof value === "string" && (PHOTONIC_DETECTOR_MODEL_VALUES as readonly string[]).includes(value);
}

function isNoiseChannelKey(value: unknown): value is CircuitNoiseChannelKey {
  return typeof value === "string" && (NOISE_CHANNEL_KEY_VALUES as readonly string[]).includes(value);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value == null) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toFiniteNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function toPngChunkType(bytes: Uint8Array, offset: number): string {
  return String.fromCharCode(bytes[offset], bytes[offset + 1], bytes[offset + 2], bytes[offset + 3]);
}

function readUint32BigEndian(bytes: Uint8Array, offset: number): number {
  return (
    ((bytes[offset] << 24) >>> 0) |
    ((bytes[offset + 1] << 16) >>> 0) |
    ((bytes[offset + 2] << 8) >>> 0) |
    (bytes[offset + 3] >>> 0)
  );
}

function writeUint32BigEndian(bytes: Uint8Array, offset: number, value: number): void {
  bytes[offset] = (value >>> 24) & 0xff;
  bytes[offset + 1] = (value >>> 16) & 0xff;
  bytes[offset + 2] = (value >>> 8) & 0xff;
  bytes[offset + 3] = value & 0xff;
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (let index = 0; index < bytes.length; index += 1) {
    const tableIndex = (crc ^ bytes[index]) & 0xff;
    crc = CRC32_TABLE[tableIndex] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

function base64ToBytes(encoded: string): Uint8Array {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function serializeCircuitPngMetadata(metadata: CircuitPreviewPngMetadata): string {
  const jsonBytes = UTF8_ENCODER.encode(JSON.stringify(metadata));
  return bytesToBase64(jsonBytes);
}

function parseCircuitPreviewPngMetadata(value: unknown): CircuitPreviewPngMetadata {
  const record = asRecord(value);
  if (!record) {
    throw new Error("Invalid metadata payload");
  }
  if (record.schema_version !== "v1") {
    throw new Error("Unsupported metadata schema");
  }

  const circuitName = typeof record.circuit_name === "string" ? record.circuit_name.trim() : "custom_design";
  const providerFamily = isCircuitProviderFamily(record.provider_family) ? record.provider_family : "unknown";
  const hardwareTarget = isCircuitHardwareTarget(record.hardware_target) ? record.hardware_target : "superconducting";
  const noiseConfigRecord = asRecord(record.noise_config);
  const noisePreset = isNoisePreset(noiseConfigRecord?.preset) ? noiseConfigRecord.preset : "medium";

  const channelRecord = asRecord(noiseConfigRecord?.channels);
  const channels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>> = {};
  if (channelRecord) {
    Object.entries(channelRecord).forEach(([key, channelValue]) => {
      if (!isNoiseChannelKey(key)) {
        return;
      }
      const channel = asRecord(channelValue);
      if (!channel) {
        return;
      }
      const enabled = typeof channel.enabled === "boolean" ? channel.enabled : true;
      const level = clamp(toFiniteNumber(channel.level, noisePresetLevel(noisePreset)), 0, 1);
      channels[key] = { enabled, level };
    });
  }

  const rawOperations = Array.isArray(record.operations) ? record.operations : [];
  const operations = rawOperations.reduce<CircuitPreviewPngMetadata["operations"]>((accumulator, rawOperation) => {
    const operationRecord = asRecord(rawOperation);
    if (!operationRecord || !isCircuitGate(operationRecord.gate)) {
      return accumulator;
    }
    const target = Math.max(0, Math.floor(toFiniteNumber(operationRecord.target, 0)));
    const nextOperation: CircuitPreviewPngMetadata["operations"][number] = {
      gate: operationRecord.gate,
      target,
    };
    if (gateNeedsControl(operationRecord.gate)) {
      const control = Math.max(0, Math.floor(toFiniteNumber(operationRecord.control, target === 0 ? 1 : 0)));
      if (control !== target) {
        nextOperation.control = control;
      }
    }
    if (gateNeedsParameter(operationRecord.gate)) {
      nextOperation.parameter = toFiniteNumber(operationRecord.parameter, 0);
    }
    accumulator.push(nextOperation);
    return accumulator;
  }, []);

  const referencedQubit = operations.reduce((maxQubit, operation) => {
    return Math.max(maxQubit, operation.target, operation.control ?? 0);
  }, 0);
  const importedQubitCount = Math.max(1, Math.floor(toFiniteNumber(record.qubit_count, referencedQubit + 1)));
  const qubitCount = clamp(Math.max(importedQubitCount, referencedQubit + 1), 1, 24);

  const boundedOperations = operations.filter((operation) => {
    if (operation.target >= qubitCount) {
      return false;
    }
    if (operation.control != null && operation.control >= qubitCount) {
      return false;
    }
    if (gateNeedsControl(operation.gate) && operation.control == null) {
      return false;
    }
    return true;
  });

  const detectorModel = isPhotonicDetectorModel(record.photonic_detector_model)
    ? record.photonic_detector_model
    : "threshold";

  const calibrationSnapshotId = typeof record.calibration_snapshot_id === "string" ? record.calibration_snapshot_id : "";
  const exportedAt = typeof record.exported_at === "string" ? record.exported_at : new Date().toISOString();

  return {
    schema_version: "v1",
    circuit_name: circuitName || "custom_design",
    provider_family: providerFamily,
    hardware_target: hardwareTarget,
    qubit_count: qubitCount,
    operations: boundedOperations,
    noise_config: {
      preset: noisePreset,
      channels,
    },
    photonic_detector_model: detectorModel,
    calibration_snapshot_id: calibrationSnapshotId,
    exported_at: exportedAt,
  };
}

function deserializeCircuitPngMetadata(encoded: string): CircuitPreviewPngMetadata {
  const decodedBytes = base64ToBytes(encoded);
  const json = UTF8_DECODER.decode(decodedBytes);
  const payload = JSON.parse(json) as unknown;
  return parseCircuitPreviewPngMetadata(payload);
}

function buildPngTextChunk(keyword: string, text: string): Uint8Array {
  const keywordBytes = UTF8_ENCODER.encode(keyword);
  const textBytes = UTF8_ENCODER.encode(text);
  const chunkDataLength = keywordBytes.length + 1 + textBytes.length;
  const chunk = new Uint8Array(4 + 4 + chunkDataLength + 4);
  writeUint32BigEndian(chunk, 0, chunkDataLength);
  chunk.set(PNG_TEXT_CHUNK_TYPE_BYTES, 4);
  chunk.set(keywordBytes, 8);
  chunk[8 + keywordBytes.length] = 0;
  chunk.set(textBytes, 9 + keywordBytes.length);
  const crc = crc32(chunk.subarray(4, 8 + chunkDataLength));
  writeUint32BigEndian(chunk, 8 + chunkDataLength, crc);
  return chunk;
}

function appendPngTextChunk(pngBytes: Uint8Array, keyword: string, text: string): Uint8Array {
  if (pngBytes.length < PNG_SIGNATURE_BYTES.length) {
    throw new Error("Invalid PNG bytes");
  }
  for (let index = 0; index < PNG_SIGNATURE_BYTES.length; index += 1) {
    if (pngBytes[index] !== PNG_SIGNATURE_BYTES[index]) {
      throw new Error("Invalid PNG signature");
    }
  }

  let offset = PNG_SIGNATURE_BYTES.length;
  let iendOffset = -1;
  while (offset + 8 <= pngBytes.length) {
    const chunkLength = readUint32BigEndian(pngBytes, offset);
    const chunkType = toPngChunkType(pngBytes, offset + 4);
    const chunkTotalLength = 12 + chunkLength;
    if (offset + chunkTotalLength > pngBytes.length) {
      throw new Error("Corrupted PNG structure");
    }
    if (chunkType === "IEND") {
      iendOffset = offset;
      break;
    }
    offset += chunkTotalLength;
  }
  if (iendOffset < 0) {
    throw new Error("PNG end marker not found");
  }

  const textChunk = buildPngTextChunk(keyword, text);
  const combined = new Uint8Array(pngBytes.length + textChunk.length);
  combined.set(pngBytes.subarray(0, iendOffset), 0);
  combined.set(textChunk, iendOffset);
  combined.set(pngBytes.subarray(iendOffset), iendOffset + textChunk.length);
  return combined;
}

function readPngTextChunk(pngBytes: Uint8Array, keyword: string): string | null {
  if (pngBytes.length < PNG_SIGNATURE_BYTES.length) {
    return null;
  }
  for (let index = 0; index < PNG_SIGNATURE_BYTES.length; index += 1) {
    if (pngBytes[index] !== PNG_SIGNATURE_BYTES[index]) {
      return null;
    }
  }
  let offset = PNG_SIGNATURE_BYTES.length;
  while (offset + 8 <= pngBytes.length) {
    const chunkLength = readUint32BigEndian(pngBytes, offset);
    const chunkType = toPngChunkType(pngBytes, offset + 4);
    const chunkDataStart = offset + 8;
    const chunkDataEnd = chunkDataStart + chunkLength;
    const chunkTotalLength = 12 + chunkLength;
    if (offset + chunkTotalLength > pngBytes.length) {
      return null;
    }
    if (chunkType === "tEXt") {
      const data = pngBytes.subarray(chunkDataStart, chunkDataEnd);
      const separatorIndex = data.indexOf(0);
      if (separatorIndex > 0) {
        const chunkKeyword = UTF8_DECODER.decode(data.subarray(0, separatorIndex));
        if (chunkKeyword === keyword) {
          return UTF8_DECODER.decode(data.subarray(separatorIndex + 1));
        }
      }
    }
    if (chunkType === "IEND") {
      break;
    }
    offset += chunkTotalLength;
  }
  return null;
}

function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }
      reject(new Error("PNG blob creation failed"));
    }, "image/png");
  });
}

function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function gatePalette(gate: CircuitGate): { fill: string; border: string; text: string } {
  if (gate === "z" || gate === "cz") {
    return { fill: "#1cb4ad", border: "#14908a", text: "#072927" };
  }
  if (gate === "measure") {
    return { fill: "#111827", border: "#090f1a", text: "#f8fafc" };
  }
  if (gate === "s" || gate === "t") {
    return { fill: "#a78bfa", border: "#7c68d4", text: "#18113a" };
  }
  if (gate === "ms" || gate === "bs") {
    return { fill: "#8da2ff", border: "#6b80df", text: "#121f49" };
  }
  if (gate === "disp" || gate === "sq" || gate === "phase") {
    return { fill: "#c0a5ff", border: "#9f7be8", text: "#2d174f" };
  }
  if (gate === "kerr" || gate === "cubic") {
    return { fill: "#f59eaf", border: "#e56a85", text: "#4e1020" };
  }
  return { fill: "#77a5f6", border: "#5e8ddf", text: "#0f2142" };
}

function drawMeasurementGlyph(
  context: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  color: string,
): void {
  context.save();
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 1.8;
  context.lineCap = "round";
  context.lineJoin = "round";

  // Meter arc.
  context.beginPath();
  context.arc(centerX, centerY + 1, 7, Math.PI, 0);
  context.stroke();

  // Needle.
  context.beginPath();
  context.moveTo(centerX, centerY + 1);
  context.lineTo(centerX + 5.5, centerY - 4.5);
  context.stroke();

  // Needle tip.
  context.beginPath();
  context.moveTo(centerX + 5.5, centerY - 4.5);
  context.lineTo(centerX + 3.7, centerY - 4.8);
  context.lineTo(centerX + 5, centerY - 6.1);
  context.closePath();
  context.fill();

  // Pivot.
  context.beginPath();
  context.arc(centerX, centerY + 1, 1.3, 0, Math.PI * 2);
  context.fill();

  // Baseline.
  context.beginPath();
  context.moveTo(centerX - 6, centerY + 5.8);
  context.lineTo(centerX + 6, centerY + 5.8);
  context.stroke();
  context.restore();
}

function roundedRectPath(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const boundedRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
  context.beginPath();
  context.moveTo(x + boundedRadius, y);
  context.arcTo(x + width, y, x + width, y + height, boundedRadius);
  context.arcTo(x + width, y + height, x, y + height, boundedRadius);
  context.arcTo(x, y + height, x, y, boundedRadius);
  context.arcTo(x, y, x + width, y, boundedRadius);
  context.closePath();
}

async function exportCircuitPreviewPng(model: CircuitPreviewExportModel): Promise<void> {
  const stepCount = Math.max(model.operations.length, 1);
  const qubitCount = Math.max(1, model.qubitCount);
  const stepWidth = 56;
  const stepGap = 18;
  const labelColumnWidth = 56;
  const paddingX = 20;
  const paddingY = 14;
  const headerHeight = 24;
  const headerGap = 10;
  const stepLabelHeight = 14;
  const stepLabelGap = 8;
  const rowHeight = 30;
  const rowGap = 10;
  const classicalGap = 16;
  const classicalHeight = 20;
  const contentWidth = labelColumnWidth + stepCount * stepWidth + (stepCount - 1) * stepGap + 28;
  const rowContentHeight = qubitCount * rowHeight + (qubitCount - 1) * rowGap;
  const contentHeight = stepLabelHeight + stepLabelGap + rowContentHeight + classicalGap + classicalHeight;
  const canvasWidth = paddingX * 2 + contentWidth;
  const canvasHeight = paddingY * 2 + headerHeight + headerGap + contentHeight;
  const pixelRatio = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  const scale = Math.max(1, Math.min(2, pixelRatio));

  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(canvasWidth * scale));
  canvas.height = Math.max(1, Math.round(canvasHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas context unavailable");
  }
  context.scale(scale, scale);

  const firstStepLeftX = paddingX + labelColumnWidth;
  const rowTop = paddingY + headerHeight + headerGap + stepLabelHeight + stepLabelGap;
  const wireStartX = firstStepLeftX - 8;
  const wireEndX = firstStepLeftX + (stepCount - 1) * (stepWidth + stepGap) + stepWidth + 8;

  const rowCenterYForQubit = (qubitIndex: number) => rowTop + qubitIndex * (rowHeight + rowGap) + rowHeight / 2;
  const stepCenterXForIndex = (stepIndex: number) => firstStepLeftX + stepIndex * (stepWidth + stepGap) + stepWidth / 2;

  context.fillStyle = "#e4e8ee";
  context.fillRect(0, 0, canvasWidth, canvasHeight);
  context.strokeStyle = "#cfd8e3";
  context.lineWidth = 1;
  context.strokeRect(0.5, 0.5, canvasWidth - 1, canvasHeight - 1);

  context.font = '700 13px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
  context.textAlign = "left";
  context.textBaseline = "middle";
  context.fillStyle = "#111827";
  context.fillText("Circuit Preview", paddingX, paddingY + headerHeight / 2);
  context.font = '600 11px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
  context.textAlign = "right";
  context.fillStyle = "#516074";
  context.fillText(
    `${hardwareTargetLabel(model.hardwareTarget)} • ${model.operations.length} gates`,
    canvasWidth - paddingX,
    paddingY + headerHeight / 2,
  );

  context.font = '500 10px "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace';
  context.textAlign = "center";
  context.fillStyle = "#5e6d80";
  for (let stepIndex = 0; stepIndex < stepCount; stepIndex += 1) {
    const label = model.operations.length === 0 ? "-" : `t${stepIndex + 1}`;
    context.fillText(label, stepCenterXForIndex(stepIndex), paddingY + headerHeight + headerGap + stepLabelHeight / 2);
  }

  for (let qubitIndex = 0; qubitIndex < qubitCount; qubitIndex += 1) {
    const rowCenterY = rowCenterYForQubit(qubitIndex);
    context.strokeStyle = "#20242b";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(wireStartX, rowCenterY);
    context.lineTo(wireEndX, rowCenterY);
    context.stroke();

    context.font = 'italic 700 13px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
    context.textAlign = "right";
    context.fillStyle = "#21252b";
    context.fillText(`q${qubitIndex}`, wireStartX - 12, rowCenterY);
  }

  const measurementSteps: Array<{ stepIndex: number; target: number }> = [];

  model.operations.forEach((operation, stepIndex) => {
    const centerX = stepCenterXForIndex(stepIndex);
    if (operation.gate === "measure") {
      const targetY = rowCenterYForQubit(operation.target);
      const palette = gatePalette("measure");
      const chipWidth = 42;
      const chipHeight = 24;
      const chipX = centerX - chipWidth / 2;
      const chipY = targetY - chipHeight / 2;
      roundedRectPath(context, chipX, chipY, chipWidth, chipHeight, 2);
      context.fillStyle = palette.fill;
      context.fill();
      context.strokeStyle = palette.border;
      context.lineWidth = 1;
      context.stroke();
      drawMeasurementGlyph(context, centerX, targetY, palette.text);

      measurementSteps.push({ stepIndex, target: operation.target });
      return;
    }

    if (gateNeedsControl(operation.gate) && operation.control != null) {
      const controlY = rowCenterYForQubit(operation.control);
      const targetY = rowCenterYForQubit(operation.target);
      context.strokeStyle = "#76a3f5";
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(centerX, Math.min(controlY, targetY));
      context.lineTo(centerX, Math.max(controlY, targetY));
      context.stroke();

      context.beginPath();
      context.fillStyle = "#6f9df3";
      context.arc(centerX, controlY, 5.5, 0, Math.PI * 2);
      context.fill();

      if (operation.gate === "cx") {
        context.beginPath();
        context.fillStyle = "#6f9df3";
        context.arc(centerX, targetY, 12, 0, Math.PI * 2);
        context.fill();
        context.strokeStyle = "#5b88db";
        context.lineWidth = 1;
        context.stroke();
        context.strokeStyle = "#f5f9ff";
        context.lineWidth = 2;
        context.beginPath();
        context.moveTo(centerX - 6, targetY);
        context.lineTo(centerX + 6, targetY);
        context.moveTo(centerX, targetY - 6);
        context.lineTo(centerX, targetY + 6);
        context.stroke();
      } else {
        const chipLabel = operation.gate === "cz" ? "Z" : gateLabel(operation.gate);
        const palette = gatePalette(operation.gate);
        const chipWidth = Math.max(24, Math.min(46, context.measureText(chipLabel).width + 16));
        const chipHeight = 24;
        const chipX = centerX - chipWidth / 2;
        const chipY = targetY - chipHeight / 2;
        roundedRectPath(context, chipX, chipY, chipWidth, chipHeight, 2);
        context.fillStyle = palette.fill;
        context.fill();
        context.strokeStyle = palette.border;
        context.lineWidth = 1;
        context.stroke();
        context.font =
          '700 12px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillStyle = palette.text;
        context.fillText(chipLabel, centerX, targetY + 0.5);
      }
      return;
    }

    const targetY = rowCenterYForQubit(operation.target);
    const label = gateNeedsParameter(operation.gate)
      ? `${gateLabel(operation.gate)}(${formatPreviewParameter(operation.parameter)})`
      : gateLabel(operation.gate);
    context.font = '700 12px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
    const textWidth = context.measureText(label).width;
    const chipWidth = Math.max(38, Math.min(64, textWidth + 14));
    const chipHeight = 24;
    const chipX = centerX - chipWidth / 2;
    const chipY = targetY - chipHeight / 2;
    const palette = gatePalette(operation.gate);
    roundedRectPath(context, chipX, chipY, chipWidth, chipHeight, 2);
    context.fillStyle = palette.fill;
    context.fill();
    context.strokeStyle = palette.border;
    context.lineWidth = 1;
    context.stroke();
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = palette.text;
    context.fillText(label, centerX, targetY + 0.5);
  });

  const classicalRowY = rowTop + rowContentHeight + classicalGap;
  context.strokeStyle = "#73859b";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(wireStartX, classicalRowY);
  context.lineTo(wireEndX, classicalRowY);
  context.moveTo(wireStartX, classicalRowY + 4);
  context.lineTo(wireEndX, classicalRowY + 4);
  context.stroke();

  context.font = 'italic 700 13px "SF Pro Text", "Segoe UI", Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
  context.textAlign = "right";
  context.textBaseline = "middle";
  context.fillStyle = "#3c495b";
  context.fillText("c", wireStartX - 12, classicalRowY + 2);
  context.font = '600 10px "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace';
  context.fillStyle = "#4f6075";
  context.fillText(`${Math.max(0, qubitCount - 1)}`, wireStartX - 8, classicalRowY - 7);

  measurementSteps.forEach((entry, bitIndex) => {
    const x = stepCenterXForIndex(entry.stepIndex);
    const sourceY = rowCenterYForQubit(entry.target) + 12;
    const targetY = classicalRowY - 3;
    context.strokeStyle = "#73859b";
    context.lineWidth = 1.5;
    context.beginPath();
    context.moveTo(x - 2, sourceY);
    context.lineTo(x - 2, targetY);
    context.moveTo(x + 2, sourceY);
    context.lineTo(x + 2, targetY);
    context.stroke();

    context.fillStyle = "#73859b";
    context.beginPath();
    context.moveTo(x - 5, targetY);
    context.lineTo(x + 5, targetY);
    context.lineTo(x, targetY + 6);
    context.closePath();
    context.fill();

    context.font = '600 10px "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace';
    context.textAlign = "left";
    context.textBaseline = "middle";
    context.fillStyle = "#3f4f64";
    context.fillText(`${bitIndex}`, x + 6, classicalRowY - 7);
  });

  const metadata: CircuitPreviewPngMetadata = {
    schema_version: "v1",
    circuit_name: model.circuitName.trim() || "custom_design",
    provider_family: model.providerFamily,
    hardware_target: model.hardwareTarget,
    qubit_count: qubitCount,
    operations: model.operations.map((operation) => ({
      gate: operation.gate,
      target: operation.target,
      control: operation.control,
      parameter: operation.parameter,
    })),
    noise_config: {
      preset: model.noisePreset,
      channels: model.noiseChannels,
    },
    photonic_detector_model: model.photonicDetectorModel,
    calibration_snapshot_id: model.calibrationSnapshotId,
    exported_at: new Date().toISOString(),
  };

  const baseBlob = await canvasToPngBlob(canvas);
  const basePngBytes = new Uint8Array(await baseBlob.arrayBuffer());
  const encodedMetadata = serializeCircuitPngMetadata(metadata);
  const pngWithMetadata = appendPngTextChunk(basePngBytes, CIRCUIT_PNG_METADATA_KEYWORD, encodedMetadata);
  const finalBlob = new Blob([pngWithMetadata.buffer as ArrayBuffer], { type: "image/png" });
  downloadBlob(`${sanitizeFileStem(model.circuitName)}_circuit.png`, finalBlob);
}

async function readCircuitMetadataFromPngFile(file: File): Promise<CircuitPreviewPngMetadata> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const encodedMetadata = readPngTextChunk(bytes, CIRCUIT_PNG_METADATA_KEYWORD);
  if (!encodedMetadata) {
    throw new Error("Metadata not found");
  }
  return deserializeCircuitPngMetadata(encodedMetadata);
}

function complex(re: number, im: number): ComplexValue {
  return { re, im };
}

function applySingleQubitMatrix(
  stateRe: Float64Array,
  stateIm: Float64Array,
  qubitCount: number,
  target: number,
  matrix: ComplexMatrix2,
) {
  const size = 1 << qubitCount;
  const mask = 1 << target;
  for (let i = 0; i < size; i += 1) {
    if ((i & mask) !== 0) {
      continue;
    }
    const j = i | mask;
    const aRe = stateRe[i];
    const aIm = stateIm[i];
    const bRe = stateRe[j];
    const bIm = stateIm[j];

    const nextARe =
      matrix.m00.re * aRe -
      matrix.m00.im * aIm +
      matrix.m01.re * bRe -
      matrix.m01.im * bIm;
    const nextAIm =
      matrix.m00.re * aIm +
      matrix.m00.im * aRe +
      matrix.m01.re * bIm +
      matrix.m01.im * bRe;
    const nextBRe =
      matrix.m10.re * aRe -
      matrix.m10.im * aIm +
      matrix.m11.re * bRe -
      matrix.m11.im * bIm;
    const nextBIm =
      matrix.m10.re * aIm +
      matrix.m10.im * aRe +
      matrix.m11.re * bIm +
      matrix.m11.im * bRe;

    stateRe[i] = nextARe;
    stateIm[i] = nextAIm;
    stateRe[j] = nextBRe;
    stateIm[j] = nextBIm;
  }
}

function applyCX(
  stateRe: Float64Array,
  stateIm: Float64Array,
  qubitCount: number,
  control: number,
  target: number,
) {
  const size = 1 << qubitCount;
  const controlMask = 1 << control;
  const targetMask = 1 << target;
  for (let i = 0; i < size; i += 1) {
    if ((i & controlMask) === 0 || (i & targetMask) !== 0) {
      continue;
    }
    const j = i | targetMask;
    const tmpRe = stateRe[i];
    const tmpIm = stateIm[i];
    stateRe[i] = stateRe[j];
    stateIm[i] = stateIm[j];
    stateRe[j] = tmpRe;
    stateIm[j] = tmpIm;
  }
}

function applyCZ(
  stateRe: Float64Array,
  stateIm: Float64Array,
  qubitCount: number,
  control: number,
  target: number,
) {
  const size = 1 << qubitCount;
  const controlMask = 1 << control;
  const targetMask = 1 << target;
  for (let i = 0; i < size; i += 1) {
    if ((i & controlMask) !== 0 && (i & targetMask) !== 0) {
      stateRe[i] *= -1;
      stateIm[i] *= -1;
    }
  }
}

function applyTwoQubitMatrix(
  stateRe: Float64Array,
  stateIm: Float64Array,
  qubitCount: number,
  qubitA: number,
  qubitB: number,
  matrix: ComplexValue[],
) {
  const size = 1 << qubitCount;
  const maskA = 1 << qubitA;
  const maskB = 1 << qubitB;
  for (let base = 0; base < size; base += 1) {
    if ((base & maskA) !== 0 || (base & maskB) !== 0) {
      continue;
    }
    const i00 = base;
    const i01 = base | maskB;
    const i10 = base | maskA;
    const i11 = base | maskA | maskB;

    const vecRe = [stateRe[i00], stateRe[i01], stateRe[i10], stateRe[i11]];
    const vecIm = [stateIm[i00], stateIm[i01], stateIm[i10], stateIm[i11]];
    const outRe = [0, 0, 0, 0];
    const outIm = [0, 0, 0, 0];

    for (let row = 0; row < 4; row += 1) {
      let accRe = 0;
      let accIm = 0;
      for (let col = 0; col < 4; col += 1) {
        const m = matrix[row * 4 + col];
        accRe += m.re * vecRe[col] - m.im * vecIm[col];
        accIm += m.re * vecIm[col] + m.im * vecRe[col];
      }
      outRe[row] = accRe;
      outIm[row] = accIm;
    }

    stateRe[i00] = outRe[0];
    stateIm[i00] = outIm[0];
    stateRe[i01] = outRe[1];
    stateIm[i01] = outIm[1];
    stateRe[i10] = outRe[2];
    stateIm[i10] = outIm[2];
    stateRe[i11] = outRe[3];
    stateIm[i11] = outIm[3];
  }
}

function measureProbabilityOne(stateRe: Float64Array, stateIm: Float64Array, qubitCount: number, target: number): number {
  const size = 1 << qubitCount;
  const mask = 1 << target;
  let probabilityOne = 0;
  for (let i = 0; i < size; i += 1) {
    if ((i & mask) !== 0) {
      probabilityOne += stateRe[i] * stateRe[i] + stateIm[i] * stateIm[i];
    }
  }
  return Math.min(1, Math.max(0, probabilityOne));
}

function normalizeState(stateRe: Float64Array, stateIm: Float64Array): boolean {
  let norm = 0;
  for (let i = 0; i < stateRe.length; i += 1) {
    norm += stateRe[i] * stateRe[i] + stateIm[i] * stateIm[i];
  }
  if (norm <= 1e-12) {
    return false;
  }
  const scale = 1 / Math.sqrt(norm);
  for (let i = 0; i < stateRe.length; i += 1) {
    stateRe[i] *= scale;
    stateIm[i] *= scale;
  }
  return true;
}

function collapseStateToBit(
  stateRe: Float64Array,
  stateIm: Float64Array,
  qubitCount: number,
  target: number,
  expectedBit: 0 | 1,
) {
  const size = 1 << qubitCount;
  const mask = 1 << target;
  for (let i = 0; i < size; i += 1) {
    const bit = (i & mask) === 0 ? 0 : 1;
    if (bit !== expectedBit) {
      stateRe[i] = 0;
      stateIm[i] = 0;
    }
  }
}

function gateMatrixForOperation(operation: CircuitOperation): ComplexMatrix2 | null {
  const theta = operation.parameter ?? 0;
  const half = theta / 2;
  const cosHalf = Math.cos(half);
  const sinHalf = Math.sin(half);
  if (operation.gate === "h") {
    const scale = 1 / Math.sqrt(2);
    return {
      m00: complex(scale, 0),
      m01: complex(scale, 0),
      m10: complex(scale, 0),
      m11: complex(-scale, 0),
    };
  }
  if (operation.gate === "x") {
    return {
      m00: complex(0, 0),
      m01: complex(1, 0),
      m10: complex(1, 0),
      m11: complex(0, 0),
    };
  }
  if (operation.gate === "y") {
    return {
      m00: complex(0, 0),
      m01: complex(0, -1),
      m10: complex(0, 1),
      m11: complex(0, 0),
    };
  }
  if (operation.gate === "z") {
    return {
      m00: complex(1, 0),
      m01: complex(0, 0),
      m10: complex(0, 0),
      m11: complex(-1, 0),
    };
  }
  if (operation.gate === "s") {
    return {
      m00: complex(1, 0),
      m01: complex(0, 0),
      m10: complex(0, 0),
      m11: complex(0, 1),
    };
  }
  if (operation.gate === "t") {
    return {
      m00: complex(1, 0),
      m01: complex(0, 0),
      m10: complex(0, 0),
      m11: complex(Math.SQRT1_2, Math.SQRT1_2),
    };
  }
  if (operation.gate === "rx") {
    return {
      m00: complex(cosHalf, 0),
      m01: complex(0, -sinHalf),
      m10: complex(0, -sinHalf),
      m11: complex(cosHalf, 0),
    };
  }
  if (operation.gate === "ry") {
    return {
      m00: complex(cosHalf, 0),
      m01: complex(-sinHalf, 0),
      m10: complex(sinHalf, 0),
      m11: complex(cosHalf, 0),
    };
  }
  if (operation.gate === "rz") {
    return {
      m00: complex(Math.cos(-half), Math.sin(-half)),
      m01: complex(0, 0),
      m10: complex(0, 0),
      m11: complex(Math.cos(half), Math.sin(half)),
    };
  }
  return null;
}

function msMatrix(theta: number): ComplexValue[] {
  const half = theta / 2;
  const cosHalf = Math.cos(half);
  const sinHalf = Math.sin(half);
  const minusI = complex(0, -sinHalf);
  return [
    complex(cosHalf, 0),
    complex(0, 0),
    complex(0, 0),
    minusI,
    complex(0, 0),
    complex(cosHalf, 0),
    minusI,
    complex(0, 0),
    complex(0, 0),
    minusI,
    complex(cosHalf, 0),
    complex(0, 0),
    minusI,
    complex(0, 0),
    complex(0, 0),
    complex(cosHalf, 0),
  ];
}

function probabilityToIntendedBit(probabilityOne: number): 0 | 1 {
  return probabilityOne >= 0.5 ? 1 : 0;
}

function pruneQubitBranches(branches: QubitBranchState[]): QubitBranchState[] {
  if (branches.length <= PREVIEW_BRANCH_LIMIT) {
    return branches;
  }
  return [...branches]
    .sort((left, right) => right.weight - left.weight)
    .slice(0, PREVIEW_BRANCH_LIMIT);
}

function runQubitMeasurementPreview(
  qubitCount: number,
  operations: CircuitOperation[],
): MeasurementPreviewRow[] {
  const size = 1 << qubitCount;
  const initRe = new Float64Array(size);
  const initIm = new Float64Array(size);
  initRe[0] = 1;
  let branches: QubitBranchState[] = [{ weight: 1, re: initRe, im: initIm }];
  const rows: MeasurementPreviewRow[] = [];

  operations.forEach((operation, index) => {
    if (operation.gate === "measure") {
      let probabilityOne = 0;
      branches.forEach((branch) => {
        probabilityOne += branch.weight * measureProbabilityOne(branch.re, branch.im, qubitCount, operation.target);
      });
      const bounded = Math.min(1, Math.max(0, probabilityOne));
      rows.push({
        label: `t${index + 1} q[${operation.target}]`,
        target: operation.target,
        probabilityZero: 1 - bounded,
        probabilityOne: bounded,
        intendedBit: probabilityToIntendedBit(bounded),
      });

      const nextBranches: QubitBranchState[] = [];
      branches.forEach((branch) => {
        const localP1 = measureProbabilityOne(branch.re, branch.im, qubitCount, operation.target);
        const localP0 = 1 - localP1;
        if (localP0 > 1e-8) {
          const re0 = new Float64Array(branch.re);
          const im0 = new Float64Array(branch.im);
          collapseStateToBit(re0, im0, qubitCount, operation.target, 0);
          if (normalizeState(re0, im0)) {
            nextBranches.push({ weight: branch.weight * localP0, re: re0, im: im0 });
          }
        }
        if (localP1 > 1e-8) {
          const re1 = new Float64Array(branch.re);
          const im1 = new Float64Array(branch.im);
          collapseStateToBit(re1, im1, qubitCount, operation.target, 1);
          if (normalizeState(re1, im1)) {
            nextBranches.push({ weight: branch.weight * localP1, re: re1, im: im1 });
          }
        }
      });
      branches = pruneQubitBranches(nextBranches);
      return;
    }

    branches.forEach((branch) => {
      if (operation.gate === "cx" && operation.control != null) {
        applyCX(branch.re, branch.im, qubitCount, operation.control, operation.target);
        return;
      }
      if (operation.gate === "cz" && operation.control != null) {
        applyCZ(branch.re, branch.im, qubitCount, operation.control, operation.target);
        return;
      }
      if (operation.gate === "ms" && operation.control != null) {
        applyTwoQubitMatrix(
          branch.re,
          branch.im,
          qubitCount,
          operation.control,
          operation.target,
          msMatrix(operation.parameter ?? Math.PI / 2),
        );
        return;
      }
      const matrix = gateMatrixForOperation(operation);
      if (!matrix) {
        return;
      }
      applySingleQubitMatrix(branch.re, branch.im, qubitCount, operation.target, matrix);
    });
  });

  return rows;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

function clamp(value: number, minValue: number, maxValue: number): number {
  if (!Number.isFinite(value)) {
    return minValue;
  }
  return Math.min(maxValue, Math.max(minValue, value));
}

function sigmoid(value: number): number {
  return 1 / (1 + Math.exp(-value));
}

function prunePhotonicBranches(branches: PhotonicBranchState[]): PhotonicBranchState[] {
  if (branches.length <= PREVIEW_BRANCH_LIMIT) {
    return branches;
  }
  return [...branches]
    .sort((left, right) => right.weight - left.weight)
    .slice(0, PREVIEW_BRANCH_LIMIT);
}

function runPhotonicMeasurementPreview(
  qubitCount: number,
  operations: CircuitOperation[],
): MeasurementPreviewRow[] {
  let branches: PhotonicBranchState[] = [
    {
      weight: 1,
      amplitude: new Float64Array(qubitCount),
      phase: new Float64Array(qubitCount),
    },
  ];
  const rows: MeasurementPreviewRow[] = [];

  operations.forEach((operation, index) => {
    if (operation.gate === "measure") {
      let probabilityOne = 0;
      branches.forEach((branch) => {
        const amplitude = Math.abs(branch.amplitude[operation.target] ?? 0);
        const phase = branch.phase[operation.target] ?? 0;
        const score = 1.35 * amplitude - 0.9 + 0.12 * Math.sin(phase);
        const localP1 = clamp01(sigmoid(score));
        probabilityOne += branch.weight * localP1;
      });
      const bounded = clamp01(probabilityOne);
      rows.push({
        label: `t${index + 1} mode[${operation.target}]`,
        target: operation.target,
        probabilityZero: 1 - bounded,
        probabilityOne: bounded,
        intendedBit: probabilityToIntendedBit(bounded),
      });

      const nextBranches: PhotonicBranchState[] = [];
      branches.forEach((branch) => {
        const amplitude = Math.abs(branch.amplitude[operation.target] ?? 0);
        const phase = branch.phase[operation.target] ?? 0;
        const score = 1.35 * amplitude - 0.9 + 0.12 * Math.sin(phase);
        const localP1 = clamp01(sigmoid(score));
        const localP0 = 1 - localP1;
        if (localP0 > 1e-8) {
          const amp0 = new Float64Array(branch.amplitude);
          const phase0 = new Float64Array(branch.phase);
          amp0[operation.target] = 0.12;
          phase0[operation.target] = 0;
          nextBranches.push({ weight: branch.weight * localP0, amplitude: amp0, phase: phase0 });
        }
        if (localP1 > 1e-8) {
          const amp1 = new Float64Array(branch.amplitude);
          const phase1 = new Float64Array(branch.phase);
          amp1[operation.target] = Math.max(1, amplitude);
          phase1[operation.target] = phase;
          nextBranches.push({ weight: branch.weight * localP1, amplitude: amp1, phase: phase1 });
        }
      });
      branches = prunePhotonicBranches(nextBranches);
      return;
    }

    branches.forEach((branch) => {
      const parameter = operation.parameter ?? 0;
      if (operation.gate === "disp") {
        branch.amplitude[operation.target] += parameter;
        return;
      }
      if (operation.gate === "sq") {
        branch.amplitude[operation.target] *= Math.exp(parameter * 0.25);
        return;
      }
      if (operation.gate === "phase") {
        branch.phase[operation.target] += parameter;
        return;
      }
      if (operation.gate === "kerr") {
        const amp = branch.amplitude[operation.target];
        branch.phase[operation.target] += parameter * amp * amp;
        return;
      }
      if (operation.gate === "cubic") {
        const amp = branch.amplitude[operation.target];
        branch.amplitude[operation.target] += 0.15 * parameter * Math.abs(amp);
        branch.phase[operation.target] += 0.35 * parameter * Math.abs(amp);
        return;
      }
      if (operation.gate === "bs" && operation.control != null) {
        const theta = parameter;
        const cosTheta = Math.cos(theta);
        const sinTheta = Math.sin(theta);
        const left = operation.control;
        const right = operation.target;
        const aLeft = branch.amplitude[left];
        const aRight = branch.amplitude[right];
        branch.amplitude[left] = cosTheta * aLeft + sinTheta * aRight;
        branch.amplitude[right] = -sinTheta * aLeft + cosTheta * aRight;
        const pLeft = branch.phase[left];
        const pRight = branch.phase[right];
        branch.phase[left] = cosTheta * pLeft + sinTheta * pRight;
        branch.phase[right] = -sinTheta * pLeft + cosTheta * pRight;
      }
    });
  });

  return rows;
}

function buildMeasurementPreviewModel(
  hardwareTarget: CircuitHardwareTarget,
  qubitCount: number,
  operations: CircuitOperation[],
): MeasurementPreviewModel {
  const warning =
    "Intended results only: computed before hardware noise injection and before syndrome-error correction/decoder policies.";

  if (!operations.some((operation) => operation.gate === "measure")) {
    return {
      warning,
      modelLabel: "Awaiting measurement gates",
      rows: [],
      unavailableReason: "Add one or more MEASURE operations to preview intended readout outcomes.",
    };
  }

  if (qubitCount > PREVIEW_MAX_QUBITS) {
    return {
      warning,
      modelLabel: "Preview limit reached",
      rows: [],
      unavailableReason: `Preview supports up to ${PREVIEW_MAX_QUBITS} qubits/modes for interactive intended-result estimation.`,
    };
  }

  if (hardwareTarget === "photonic") {
    return {
      warning,
      modelLabel: "Photonic mode model (Gaussian + non-Gaussian idealized projection)",
      rows: runPhotonicMeasurementPreview(qubitCount, operations),
    };
  }

  const modelLabel =
    hardwareTarget === "trapped_ion"
      ? "Trapped-ion unitary model (ideal MS/R-rotations)"
      : "Superconducting unitary model (ideal gate matrix)";
  return {
    warning,
    modelLabel,
    rows: runQubitMeasurementPreview(qubitCount, operations),
  };
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function averageNoiseIntensity(
  noisePreset: CircuitNoisePreset,
  noiseChannels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>>,
  noiseOptions: NoiseChannelOption[],
): { intensity: number; activeCount: number } {
  const enabledLevels = noiseOptions
    .map((option) => noiseChannels[option.key])
    .filter((channel): channel is CircuitNoiseChannelConfig => Boolean(channel?.enabled))
    .map((channel) => clamp01(channel.level));
  if (enabledLevels.length > 0) {
    const intensity = enabledLevels.reduce((sum, level) => sum + level, 0) / enabledLevels.length;
    return { intensity, activeCount: enabledLevels.length };
  }
  if (noisePreset !== "custom") {
    return { intensity: noisePresetLevel(noisePreset), activeCount: 0 };
  }
  return { intensity: 0, activeCount: 0 };
}

function buildCouplingMap(hardwareTarget: CircuitHardwareTarget, qubitCount: number): Array<[number, number]> {
  if (qubitCount <= 1) {
    return [];
  }
  if (hardwareTarget === "trapped_ion") {
    const edges: Array<[number, number]> = [];
    for (let left = 0; left < qubitCount; left += 1) {
      for (let right = left + 1; right < qubitCount; right += 1) {
        edges.push([left, right]);
      }
    }
    return edges;
  }
  const linear: Array<[number, number]> = [];
  for (let q = 0; q < qubitCount - 1; q += 1) {
    linear.push([q, q + 1]);
  }
  return linear;
}

function nativeDurationNs(hardwareTarget: CircuitHardwareTarget, gate: string): number {
  if (hardwareTarget === "trapped_ion") {
    if (gate === "ms") {
      return 230;
    }
    if (gate === "measure") {
      return 900;
    }
    if (gate === "rx") {
      return 40;
    }
    return 25;
  }
  if (hardwareTarget === "photonic") {
    if (gate === "disp") {
      return 55;
    }
    if (gate === "sq") {
      return 70;
    }
    if (gate === "phase") {
      return 28;
    }
    if (gate === "bs") {
      return 95;
    }
    if (gate === "kerr") {
      return 170;
    }
    if (gate === "cubic") {
      return 220;
    }
    return 760;
  }
  if (gate === "measure") {
    return 820;
  }
  if (gate === "cx") {
    return 320;
  }
  if (gate === "x") {
    return 60;
  }
  if (gate === "sx") {
    return 45;
  }
  return 35;
}

function pushCompiledOperation(
  target: CircuitCompiledOperation[],
  hardwareTarget: CircuitHardwareTarget,
  gate: string,
  sourceIndex: number,
  qubitTarget: number,
  qubitControl?: number,
  parameter?: number,
) {
  target.push({
    gate,
    target: qubitTarget,
    control: qubitControl,
    parameter,
    duration_ns: nativeDurationNs(hardwareTarget, gate),
    source_index: sourceIndex,
  });
}

function appendSuperconductingSingle(
  target: CircuitCompiledOperation[],
  sourceIndex: number,
  logicalTarget: number,
  gate: CircuitGate,
  parameter: number | undefined,
) {
  const theta = parameter ?? 0;
  if (gate === "x") {
    pushCompiledOperation(target, "superconducting", "x", sourceIndex, logicalTarget);
    return;
  }
  if (gate === "z") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI);
    return;
  }
  if (gate === "s") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    return;
  }
  if (gate === "t") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 4);
    return;
  }
  if (gate === "h") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    return;
  }
  if (gate === "y") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "superconducting", "x", sourceIndex, logicalTarget);
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, -Math.PI / 2);
    return;
  }
  if (gate === "rx") {
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, theta);
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, -Math.PI / 2);
    return;
  }
  if (gate === "ry") {
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, theta);
    pushCompiledOperation(target, "superconducting", "sx", sourceIndex, logicalTarget);
    return;
  }
  pushCompiledOperation(target, "superconducting", "rz", sourceIndex, logicalTarget, undefined, theta);
}

function appendTrappedIonSingle(
  target: CircuitCompiledOperation[],
  sourceIndex: number,
  logicalTarget: number,
  gate: CircuitGate,
  parameter: number | undefined,
) {
  const theta = parameter ?? 0;
  if (gate === "x") {
    pushCompiledOperation(target, "trapped_ion", "rx", sourceIndex, logicalTarget, undefined, Math.PI);
    return;
  }
  if (gate === "y") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "trapped_ion", "rx", sourceIndex, logicalTarget, undefined, Math.PI);
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, -Math.PI / 2);
    return;
  }
  if (gate === "z") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI);
    return;
  }
  if (gate === "h") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "trapped_ion", "rx", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    return;
  }
  if (gate === "s") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    return;
  }
  if (gate === "t") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 4);
    return;
  }
  if (gate === "ry") {
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, Math.PI / 2);
    pushCompiledOperation(target, "trapped_ion", "rx", sourceIndex, logicalTarget, undefined, theta);
    pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, -Math.PI / 2);
    return;
  }
  if (gate === "rx") {
    pushCompiledOperation(target, "trapped_ion", "rx", sourceIndex, logicalTarget, undefined, theta);
    return;
  }
  pushCompiledOperation(target, "trapped_ion", "rz", sourceIndex, logicalTarget, undefined, theta);
}

function scheduleCompiledDepth(
  operations: CircuitCompiledOperation[],
  qubitCount: number,
  trackEntanglingConflicts: boolean,
): { depth: number; conflicts: number } {
  const lastLayer = Array.from({ length: qubitCount }, () => 0);
  const lastEntangling = Array.from({ length: qubitCount }, () => -100);
  let depth = 0;
  let conflicts = 0;

  operations.forEach((operation) => {
    const participants: number[] = operation.control != null
      ? [operation.target, operation.control]
      : [operation.target];
    let layer = 1;
    participants.forEach((q) => {
      layer = Math.max(layer, lastLayer[q] + 1);
    });
    if (trackEntanglingConflicts && operation.control != null) {
      participants.forEach((q) => {
        if (layer - lastEntangling[q] <= 1) {
          conflicts += 1;
        }
        lastEntangling[q] = layer;
      });
    }
    participants.forEach((q) => {
      lastLayer[q] = layer;
    });
    depth = Math.max(depth, layer);
  });
  return { depth, conflicts };
}

function buildCircuitCompileArtifact(
  providerFamily: CircuitProviderFamily,
  hardwareTarget: CircuitHardwareTarget,
  qubitCount: number,
  operations: CircuitOperation[],
  sourceDepth: number,
  noisePreset: CircuitNoisePreset,
  noiseChannels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>>,
  noiseOptions: NoiseChannelOption[],
  photonicDetectorModel: PhotonicDetectorModel,
  calibrationSnapshot: VendorCalibrationSnapshot | null,
): CircuitCompileArtifact {
  const transpiled: CircuitCompiledOperation[] = [];
  const warnings: string[] = [];
  let swapInsertions = 0;
  const couplingMap = buildCouplingMap(hardwareTarget, qubitCount);
  const nativeBasis =
    hardwareTarget === "photonic"
      ? ["disp", "sq", "phase", "bs", "kerr", "cubic", "measure"]
      : hardwareTarget === "trapped_ion"
        ? ["rz", "rx", "ms", "measure"]
        : ["rz", "sx", "x", "cx", "measure"];

  if (hardwareTarget === "superconducting") {
    const physicalOfLogical = Array.from({ length: qubitCount }, (_, index) => index);
    const logicalOfPhysical = Array.from({ length: qubitCount }, (_, index) => index);
    const appendSwap = (left: number, right: number, sourceIndex: number) => {
      pushCompiledOperation(transpiled, "superconducting", "cx", sourceIndex, right, left);
      pushCompiledOperation(transpiled, "superconducting", "cx", sourceIndex, left, right);
      pushCompiledOperation(transpiled, "superconducting", "cx", sourceIndex, right, left);
      swapInsertions += 1;
      const logicalLeft = logicalOfPhysical[left];
      const logicalRight = logicalOfPhysical[right];
      logicalOfPhysical[left] = logicalRight;
      logicalOfPhysical[right] = logicalLeft;
      physicalOfLogical[logicalLeft] = right;
      physicalOfLogical[logicalRight] = left;
    };

    operations.forEach((operation, sourceIndex) => {
      if (operation.gate === "measure") {
        pushCompiledOperation(
          transpiled,
          "superconducting",
          "measure",
          sourceIndex,
          physicalOfLogical[operation.target],
        );
        return;
      }
      if (operation.gate === "cx" || operation.gate === "cz") {
        if (operation.control == null) {
          return;
        }
        let physicalControl = physicalOfLogical[operation.control];
        let physicalTarget = physicalOfLogical[operation.target];
        while (Math.abs(physicalControl - physicalTarget) > 1) {
          const step = physicalControl < physicalTarget ? 1 : -1;
          appendSwap(physicalControl, physicalControl + step, sourceIndex);
          physicalControl = physicalOfLogical[operation.control];
          physicalTarget = physicalOfLogical[operation.target];
        }
        if (operation.gate === "cz") {
          appendSuperconductingSingle(
            transpiled,
            sourceIndex,
            physicalTarget,
            "h",
            undefined,
          );
          pushCompiledOperation(
            transpiled,
            "superconducting",
            "cx",
            sourceIndex,
            physicalTarget,
            physicalControl,
          );
          appendSuperconductingSingle(
            transpiled,
            sourceIndex,
            physicalTarget,
            "h",
            undefined,
          );
        } else {
          pushCompiledOperation(
            transpiled,
            "superconducting",
            "cx",
            sourceIndex,
            physicalTarget,
            physicalControl,
          );
        }
        return;
      }
      if (operation.gate === "ms") {
        warnings.push("MS gate is not native to superconducting hardware; compiled to CX + single-qubit approximations.");
        if (operation.control != null) {
          const physicalControl = physicalOfLogical[operation.control];
          const physicalTarget = physicalOfLogical[operation.target];
          pushCompiledOperation(
            transpiled,
            "superconducting",
            "cx",
            sourceIndex,
            physicalTarget,
            physicalControl,
          );
          appendSuperconductingSingle(transpiled, sourceIndex, physicalTarget, "rz", operation.parameter ?? Math.PI / 2);
          pushCompiledOperation(
            transpiled,
            "superconducting",
            "cx",
            sourceIndex,
            physicalTarget,
            physicalControl,
          );
        }
        return;
      }
      appendSuperconductingSingle(
        transpiled,
        sourceIndex,
        physicalOfLogical[operation.target],
        operation.gate,
        operation.parameter,
      );
    });
  } else if (hardwareTarget === "trapped_ion") {
    operations.forEach((operation, sourceIndex) => {
      if (operation.gate === "measure") {
        pushCompiledOperation(transpiled, "trapped_ion", "measure", sourceIndex, operation.target);
        return;
      }
      if (operation.gate === "cx" || operation.gate === "cz") {
        if (operation.control == null) {
          return;
        }
        if (operation.gate === "cx") {
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rz",
            sourceIndex,
            operation.target,
            undefined,
            -Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "ms",
            sourceIndex,
            operation.target,
            operation.control,
            Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rx",
            sourceIndex,
            operation.control,
            undefined,
            -Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rx",
            sourceIndex,
            operation.target,
            undefined,
            Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rz",
            sourceIndex,
            operation.target,
            undefined,
            Math.PI / 2,
          );
        } else {
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "ms",
            sourceIndex,
            operation.target,
            operation.control,
            Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rz",
            sourceIndex,
            operation.control,
            undefined,
            Math.PI / 2,
          );
          pushCompiledOperation(
            transpiled,
            "trapped_ion",
            "rz",
            sourceIndex,
            operation.target,
            undefined,
            Math.PI / 2,
          );
        }
        return;
      }
      appendTrappedIonSingle(transpiled, sourceIndex, operation.target, operation.gate, operation.parameter);
    });
  } else {
    operations.forEach((operation, sourceIndex) => {
      if (operation.gate === "measure") {
        pushCompiledOperation(transpiled, "photonic", "measure", sourceIndex, operation.target);
        return;
      }
      pushCompiledOperation(
        transpiled,
        "photonic",
        operation.gate,
        sourceIndex,
        operation.target,
        operation.control,
        operation.parameter,
      );
    });
  }

  const { depth: transpiledDepth, conflicts } = scheduleCompiledDepth(
    transpiled,
    qubitCount,
    hardwareTarget === "trapped_ion",
  );
  const totalDurationNs = transpiled.reduce((sum, operation) => sum + operation.duration_ns, 0);

  const nonGaussianCount = transpiled.filter((op) => op.gate === "kerr" || op.gate === "cubic").length;
  const gaussianCount = transpiled.filter(
    (op) => op.gate === "disp" || op.gate === "sq" || op.gate === "phase" || op.gate === "bs",
  ).length;
  if (operations.every((operation) => operation.gate !== "measure")) {
    warnings.push("No measurement gate found; add MEASURE to produce deterministic readout targets.");
  }
  if (hardwareTarget === "photonic" && nonGaussianCount === 0) {
    warnings.push("Photonic program is Gaussian-only; add KERR/CUBIC for non-Gaussian injection workflows.");
  }
  if (hardwareTarget === "superconducting" && swapInsertions > 0) {
    warnings.push(
      `Nearest-neighbor routing inserted ${swapInsertions} SWAP operations to satisfy coupling constraints.`,
    );
  }
  if (hardwareTarget === "trapped_ion" && conflicts > 0) {
    warnings.push(
      `Ion-chain schedule has ${conflicts} immediate entangling cooldown conflict(s); expect timing stretch.`,
    );
  }
  if (hardwareTarget === "photonic") {
    const amplitudes = new Float64Array(qubitCount);
    operations.forEach((operation) => {
      const parameter = operation.parameter ?? 0;
      if (operation.gate === "disp") {
        amplitudes[operation.target] += Math.abs(parameter);
      } else if (operation.gate === "sq") {
        amplitudes[operation.target] *= Math.exp(Math.abs(parameter) * 0.25);
      } else if (operation.gate === "kerr" || operation.gate === "cubic") {
        amplitudes[operation.target] += Math.abs(parameter) * 0.3;
      }
    });
    const maxAmplitude = Math.max(0, ...Array.from(amplitudes));
    if (maxAmplitude > 3.5) {
      warnings.push("Estimated mode energy exceeds cutoff guidance (n_cut≈12); reduce displacement/squeezing.");
    }
    if (photonicDetectorModel === "threshold" && nonGaussianCount > 0) {
      warnings.push("Threshold detector selected with non-Gaussian gates; PNR approximation improves parity diagnostics.");
    }
    if (gaussianCount === 0 && nonGaussianCount > 0) {
      warnings.push("Non-Gaussian-only stack may be numerically stiff; consider Gaussian preconditioning stages.");
    }
  }

  const noise = averageNoiseIntensity(noisePreset, noiseChannels, noiseOptions);
  const twoQubitCount = transpiled.filter((operation) => operation.control != null).length;
  const roundsEst = Math.max(2, Math.min(12, Math.ceil(Math.max(1, transpiledDepth) / 3)));
  const stabilizerCount = Math.max(1, hardwareTarget === "photonic" ? qubitCount : 2 * qubitCount - 2);
  const eventBase = (twoQubitCount + 1) * roundsEst * (0.45 + noise.intensity * 0.95);
  const xEvents = Math.max(0, Math.round(eventBase * (hardwareTarget === "photonic" ? 0.43 : 0.52)));
  const zEvents = Math.max(0, Math.round(eventBase * (hardwareTarget === "photonic" ? 0.57 : 0.48)));
  const logicalHint = clamp01((xEvents + zEvents) / Math.max(20, stabilizerCount * roundsEst * 12));

  return {
    schema_version: "v1",
    hardware_target: hardwareTarget,
    provider_family: providerFamily,
    calibration_snapshot_id: calibrationSnapshot?.id ?? "",
    calibration_vendor: calibrationSnapshot?.vendor ?? "",
    calibration_backend: calibrationSnapshot?.backend ?? "",
    calibration_captured_at: calibrationSnapshot?.capturedAt ?? "",
    calibration_source: calibrationSnapshot?.source ?? "",
    native_basis: nativeBasis,
    coupling_map: couplingMap,
    photonic_detector_model: photonicDetectorModel,
    source_depth: sourceDepth,
    transpiled_depth: transpiledDepth,
    source_gate_count: operations.length,
    transpiled_gate_count: transpiled.length,
    swap_insertions: swapInsertions,
    schedule_conflicts: conflicts,
    total_duration_ns: totalDurationNs,
    warnings,
    syndrome_preview: {
      rounds_est: roundsEst,
      stabilizer_count_est: stabilizerCount,
      x_events_est: xEvents,
      z_events_est: zEvents,
      logical_error_hint: logicalHint,
    },
    transpiled_operations: transpiled,
  };
}

function buildCircuitCompileReport(
  artifact: CircuitCompileArtifact,
  noiseIntensity: number,
  activeNoiseCount: number,
  noiseOptionCount: number,
  hardwareTarget: CircuitHardwareTarget,
  calibrationSnapshot: VendorCalibrationSnapshot | null,
): CircuitCompileReport {
  const measurementCount = artifact.transpiled_operations.filter((operation) => operation.gate === "measure").length;
  const twoQubitCount = artifact.transpiled_operations.filter((operation) => operation.control != null).length;
  const oneQubitCount = Math.max(0, artifact.transpiled_operations.length - measurementCount - twoQubitCount);
  const parameterizedCount = artifact.transpiled_operations.filter((operation) => operation.parameter != null).length;
  const gaussianCount = artifact.transpiled_operations.filter(
    (operation) =>
      operation.gate === "disp" ||
      operation.gate === "sq" ||
      operation.gate === "phase" ||
      operation.gate === "bs",
  ).length;
  const nonGaussianCount = artifact.transpiled_operations.filter(
    (operation) => operation.gate === "kerr" || operation.gate === "cubic",
  ).length;

  const calibration = calibrationScaleFactors(hardwareTarget, calibrationSnapshot);
  const durationMicros = artifact.total_duration_ns / 1000;
  const timingPenalty = Math.min(0.16, (durationMicros / 180.0) * calibration.timingScale);
  const infidelityBase =
    oneQubitCount * 0.0009 * calibration.oneQubitScale +
    twoQubitCount *
      (hardwareTarget === "trapped_ion" ? 0.0078 : hardwareTarget === "photonic" ? 0.011 : 0.0105) *
      calibration.twoQubitScale +
    measurementCount * 0.0055 * calibration.measurementScale +
    artifact.swap_insertions * 0.004 +
    artifact.schedule_conflicts * 0.005 +
    Math.max(0, calibration.backgroundScale - 1.0) * 0.01 +
    Math.max(0, calibration.zBiasScale - 1.0) * 0.006;
  const noisePenalty = infidelityBase * (0.5 + noiseIntensity * 0.95);
  const infidelity = clamp01(noisePenalty + timingPenalty);
  const center = clamp01(1 - infidelity);
  const spread = Math.min(0.28, 0.03 + noiseIntensity * 0.11 + twoQubitCount * 0.0015);
  const fidelityLow = clamp01(center - spread * 0.5);
  const fidelityHigh = clamp01(center + spread * 0.5);

  const profileLabel =
    hardwareTarget === "trapped_ion"
      ? "Trapped-ion compiler profile"
      : hardwareTarget === "photonic"
        ? "Photonic compiler profile"
        : "Superconducting compiler profile";

  const metrics: CompileMetricRow[] = [
    { label: "Native Gate Compliance", value: "100%" },
    { label: "Source Depth", value: `${artifact.source_depth}` },
    { label: "Transpiled Depth", value: `${artifact.transpiled_depth}` },
    { label: "Transpiled Gate Count", value: `${artifact.transpiled_gate_count}` },
    { label: "One-Qubit Gates", value: `${oneQubitCount}` },
    { label: "Two-Qubit Gates", value: `${twoQubitCount}` },
    { label: "Measurement Gates", value: `${measurementCount}` },
    { label: "Parameterized Gates", value: `${parameterizedCount}` },
    { label: "Total Program Duration (Est.)", value: `${durationMicros.toFixed(2)} μs` },
    { label: "Active Noise Channels", value: `${activeNoiseCount}/${noiseOptionCount}` },
    { label: "Syndrome X Events (Est.)", value: `${artifact.syndrome_preview.x_events_est}` },
    { label: "Syndrome Z Events (Est.)", value: `${artifact.syndrome_preview.z_events_est}` },
    { label: "Logical Error Hint", value: formatPercent(artifact.syndrome_preview.logical_error_hint) },
  ];

  if (calibrationSnapshot) {
    metrics.push({ label: "Calibration Snapshot", value: calibrationSnapshot.label });
    metrics.push({ label: "Calibration Vendor", value: calibrationSnapshot.vendor.toUpperCase() });
  }

  if (hardwareTarget === "superconducting") {
    metrics.push({ label: "SWAP Insertions", value: `${artifact.swap_insertions}` });
  }
  if (hardwareTarget === "trapped_ion") {
    metrics.push({ label: "Schedule Conflicts", value: `${artifact.schedule_conflicts}` });
  }
  if (hardwareTarget === "photonic") {
    metrics.push({ label: "Gaussian Gates", value: `${gaussianCount}` });
    metrics.push({ label: "Non-Gaussian Gates", value: `${nonGaussianCount}` });
    metrics.push({ label: "Detector Model", value: artifact.photonic_detector_model });
  }

  return {
    profileLabel,
    fidelityBand: `${formatPercent(fidelityLow)} - ${formatPercent(fidelityHigh)}`,
    warnings: artifact.warnings,
    metrics,
  };
}

function buildArtifactJson(artifact: CircuitCompileArtifact): string {
  return JSON.stringify(artifact, null, 2);
}

function previewCellForOperation(
  operation: CircuitOperation | undefined,
  qubitIndex: number,
): CircuitPreviewCellModel {
  if (!operation) {
    return { kind: "wire", label: null, hasConnector: false };
  }

  if (gateNeedsControl(operation.gate) && operation.control != null) {
    const low = Math.min(operation.control, operation.target);
    const high = Math.max(operation.control, operation.target);
    const hasConnector = qubitIndex >= low && qubitIndex <= high;
    if (qubitIndex === operation.control) {
      return { kind: "control", label: null, hasConnector };
    }
    if (qubitIndex === operation.target) {
      const targetLabel =
        operation.gate === "cx"
          ? "X"
          : operation.gate === "cz"
            ? "Z"
            : operation.gate === "ms"
              ? "MS"
              : operation.gate === "bs"
                ? "BS"
                : gateLabel(operation.gate);
      return {
        kind: "target",
        label: targetLabel,
        hasConnector,
      };
    }
    return { kind: "wire", label: null, hasConnector };
  }

  if (qubitIndex !== operation.target) {
    return { kind: "wire", label: null, hasConnector: false };
  }
  if (operation.gate === "measure") {
    return { kind: "measure", label: "M", hasConnector: false };
  }
  if (gateNeedsParameter(operation.gate)) {
    return {
      kind: "gate",
      label: `${operation.gate.toUpperCase()}(${formatPreviewParameter(operation.parameter)})`,
      hasConnector: false,
    };
  }
  return { kind: "gate", label: operation.gate.toUpperCase(), hasConnector: false };
}

export function StartCircuitDesignDialog({
  open,
  pending,
  providerName,
  providerFamily,
  onClose,
  onStart,
}: StartCircuitDesignDialogProps) {
  const [circuitName, setCircuitName] = useState("custom_design");
  const [qubitCount, setQubitCount] = useState(3);
  const [selectedGate, setSelectedGate] = useState<CircuitGate>("h");
  const [targetQubit, setTargetQubit] = useState(0);
  const [controlQubit, setControlQubit] = useState(1);
  const [parameterInput, setParameterInput] = useState("1.5708");
  const [operations, setOperations] = useState<CircuitOperation[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const importPngInputRef = useRef<HTMLInputElement | null>(null);
  const [runtimeCalibrationSnapshots, setRuntimeCalibrationSnapshots] = useState<VendorCalibrationSnapshot[]>([]);
  const hardwareTargets = useMemo(() => hardwareTargetsForProvider(providerFamily), [providerFamily]);
  const [hardwareTarget, setHardwareTarget] = useState<CircuitHardwareTarget>(hardwareTargets[0] ?? "superconducting");
  const calibrationOptions = useMemo(
    () => calibrationSnapshotsForContext(providerFamily, hardwareTarget, runtimeCalibrationSnapshots),
    [providerFamily, hardwareTarget, runtimeCalibrationSnapshots],
  );
  const [calibrationSnapshotId, setCalibrationSnapshotId] = useState<string>(() => {
    const defaultId = defaultCalibrationSnapshotId(
      providerFamily,
      hardwareTargets[0] ?? "superconducting",
      runtimeCalibrationSnapshots,
    );
    return defaultId ?? "";
  });
  const availableGates = useMemo(() => gateOptionsForHardwareTarget(hardwareTarget), [hardwareTarget]);
  const noiseOptions = useMemo(() => noiseOptionsForHardwareTarget(hardwareTarget), [hardwareTarget]);
  const [noisePreset, setNoisePreset] = useState<CircuitNoisePreset>("medium");
  const [noiseChannels, setNoiseChannels] = useState<Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>>>(
    () => buildNoiseStateFromPreset(noiseOptionsForHardwareTarget("superconducting"), "medium"),
  );
  const [photonicDetectorModel, setPhotonicDetectorModel] = useState<PhotonicDetectorModel>("threshold");
  const selectedCalibrationSnapshot = useMemo(
    () => calibrationOptions.find((snapshot) => snapshot.id === calibrationSnapshotId) ?? null,
    [calibrationOptions, calibrationSnapshotId],
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    apiFetch<{ snapshots?: unknown }>("/system/calibrations")
      .then((catalog) => {
        if (cancelled) {
          return;
        }
        const snapshots = normalizeVendorCalibrationSnapshots(catalog?.snapshots);
        if (snapshots.length > 0) {
          setRuntimeCalibrationSnapshots(snapshots);
        }
      })
      .catch(() => {
        // keep static fallback
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setCircuitName("custom_design");
    setQubitCount(3);
    const initialGate = gateOptionsForHardwareTarget(hardwareTargets[0] ?? "superconducting")[0]?.value ?? "h";
    setSelectedGate(initialGate);
    setTargetQubit(0);
    setControlQubit(1);
    setParameterInput("1.5708");
    setOperations([]);
    setHardwareTarget(hardwareTargets[0] ?? "superconducting");
    setCalibrationSnapshotId(
      defaultCalibrationSnapshotId(
        providerFamily,
        hardwareTargets[0] ?? "superconducting",
        runtimeCalibrationSnapshots,
      ) ?? "",
    );
    setNoisePreset("medium");
    setNoiseChannels(buildNoiseStateFromPreset(noiseOptionsForHardwareTarget(hardwareTargets[0] ?? "superconducting"), "medium"));
    setPhotonicDetectorModel("threshold");
    setErrorMessage(null);
  }, [open, hardwareTargets, providerFamily, runtimeCalibrationSnapshots]);

  useEffect(() => {
    setTargetQubit((current) => Math.min(current, Math.max(0, qubitCount - 1)));
    setControlQubit((current) => Math.min(current, Math.max(0, qubitCount - 1)));
  }, [qubitCount]);

  useEffect(() => {
    if (hardwareTargets.includes(hardwareTarget)) {
      return;
    }
    setHardwareTarget(hardwareTargets[0] ?? "superconducting");
  }, [hardwareTargets, hardwareTarget]);

  useEffect(() => {
    if (calibrationOptions.some((option) => option.id === calibrationSnapshotId)) {
      return;
    }
    const defaultId = defaultCalibrationSnapshotId(
      providerFamily,
      hardwareTarget,
      runtimeCalibrationSnapshots,
    );
    setCalibrationSnapshotId(defaultId ?? calibrationOptions[0]?.id ?? "");
  }, [calibrationOptions, calibrationSnapshotId, providerFamily, hardwareTarget, runtimeCalibrationSnapshots]);

  useEffect(() => {
    const selectedSupported = availableGates.some((option) => option.value === selectedGate);
    if (selectedSupported) {
      return;
    }
    setSelectedGate(availableGates[0]?.value ?? "h");
  }, [availableGates, selectedGate]);

  useEffect(() => {
    setNoiseChannels((current) => {
      const next: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>> = {};
      noiseOptions.forEach((option) => {
        const existing = current[option.key];
        next[option.key] = existing ?? {
          enabled: true,
          level: noisePreset === "custom" ? 0.5 : noisePresetLevel(noisePreset),
        };
      });
      return next;
    });
  }, [noiseOptions, noisePreset]);

  const qubitOptions = useMemo(
    () => Array.from({ length: qubitCount }, (_, index) => index),
    [qubitCount],
  );
  const qasmPreview = useMemo(() => buildQasm(qubitCount, operations), [operations, qubitCount]);
  const estimatedDepth = useMemo(() => estimateDepth(qubitCount, operations), [operations, qubitCount]);
  const measurementPreview = useMemo(
    () => buildMeasurementPreviewModel(hardwareTarget, qubitCount, operations),
    [hardwareTarget, operations, qubitCount],
  );
  const noiseSummary = useMemo(
    () => averageNoiseIntensity(noisePreset, noiseChannels, noiseOptions),
    [noisePreset, noiseChannels, noiseOptions],
  );
  const compileArtifact = useMemo(
    () =>
      buildCircuitCompileArtifact(
        providerFamily,
        hardwareTarget,
        qubitCount,
        operations,
        estimatedDepth,
        noisePreset,
        noiseChannels,
        noiseOptions,
        photonicDetectorModel,
        selectedCalibrationSnapshot,
      ),
    [
      providerFamily,
      hardwareTarget,
      qubitCount,
      operations,
      estimatedDepth,
      noisePreset,
      noiseChannels,
      noiseOptions,
      photonicDetectorModel,
      selectedCalibrationSnapshot,
    ],
  );
  const compileArtifactJson = useMemo(() => buildArtifactJson(compileArtifact), [compileArtifact]);
  const compileReport = useMemo(
    () =>
      buildCircuitCompileReport(
        compileArtifact,
        noiseSummary.intensity,
        noiseSummary.activeCount,
        noiseOptions.length,
        hardwareTarget,
        selectedCalibrationSnapshot,
      ),
    [
      compileArtifact,
      noiseSummary.intensity,
      noiseSummary.activeCount,
      noiseOptions.length,
      hardwareTarget,
      selectedCalibrationSnapshot,
    ],
  );
  const touchedQubits = useMemo(() => {
    const set = new Set<number>();
    operations.forEach((operation) => {
      set.add(operation.target);
      if (operation.control != null) {
        set.add(operation.control);
      }
    });
    return set;
  }, [operations]);
  const intendedEndStateByQubit = useMemo(() => {
    const map = new Map<number, MeasurementPreviewRow>();
    measurementPreview.rows.forEach((row) => {
      map.set(row.target, row);
    });
    return map;
  }, [measurementPreview.rows]);
  const previewStepCount = Math.max(operations.length, 1);
  const previewGridTemplate = useMemo(
    () => `70px 50px repeat(${previewStepCount}, minmax(72px, 1fr)) 70px`,
    [previewStepCount],
  );

  if (!open) {
    return null;
  }

  const addOperation = () => {
    const operation: CircuitOperation = {
      id: nextOperationId(),
      gate: selectedGate,
      target: targetQubit,
    };
    if (gateNeedsControl(selectedGate)) {
      if (controlQubit === targetQubit) {
        setErrorMessage("Control and target qubits must be different.");
        return;
      }
      operation.control = controlQubit;
    }
    if (gateNeedsParameter(selectedGate)) {
      const parsed = Number.parseFloat(parameterInput);
      if (!Number.isFinite(parsed)) {
        setErrorMessage("Parameter must be a valid numeric value.");
        return;
      }
      operation.parameter = parsed;
    }
    setOperations((current) => [...current, operation]);
    setErrorMessage(null);
  };

  const removeOperation = (id: string) => {
    setOperations((current) => current.filter((operation) => operation.id !== id));
  };

  const moveOperation = (id: string, direction: "up" | "down") => {
    setOperations((current) => {
      const index = current.findIndex((operation) => operation.id === id);
      if (index < 0) {
        return current;
      }
      const nextIndex = direction === "up" ? index - 1 : index + 1;
      if (nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
  };

  const applyNoisePreset = (preset: CircuitNoisePreset) => {
    setNoisePreset(preset);
    if (preset === "custom") {
      return;
    }
    setNoiseChannels(buildNoiseStateFromPreset(noiseOptions, preset));
  };

  const toggleNoiseChannel = (key: CircuitNoiseChannelKey) => {
    setNoisePreset("custom");
    setNoiseChannels((current) => {
      const existing = current[key] ?? { enabled: true, level: 0.5 };
      return {
        ...current,
        [key]: {
          ...existing,
          enabled: !existing.enabled,
        },
      };
    });
  };

  const setNoiseChannelLevel = (key: CircuitNoiseChannelKey, level: number) => {
    const bounded = Math.max(0, Math.min(1, level));
    setNoisePreset("custom");
    setNoiseChannels((current) => {
      const existing = current[key] ?? { enabled: true, level: 0.5 };
      return {
        ...current,
        [key]: {
          ...existing,
          level: bounded,
        },
      };
    });
  };

  const handleStart = () => {
    if (operations.length === 0) {
      setErrorMessage("Add at least one gate operation before starting.");
      return;
    }
    onStart({
      name: circuitName.trim() || "custom_design",
      qubitCount,
      operations,
      qasm: qasmPreview,
      depth: estimatedDepth,
      gateCount: operations.length,
      hardwareTarget,
      noiseConfig: {
        preset: noisePreset,
        channels: noiseChannels,
      },
      compileArtifact,
      calibrationSnapshotId: selectedCalibrationSnapshot?.id,
    });
  };

  const applyImportedCircuitMetadata = (metadata: CircuitPreviewPngMetadata) => {
    const fallbackTarget = hardwareTargets[0] ?? "superconducting";
    const resolvedTarget = hardwareTargets.includes(metadata.hardware_target) ? metadata.hardware_target : fallbackTarget;
    const supportedGateValues = new Set(gateOptionsForHardwareTarget(resolvedTarget).map((gate) => gate.value));

    const referencedQubit = metadata.operations.reduce((maxQubit, operation) => {
      return Math.max(maxQubit, operation.target, operation.control ?? 0);
    }, 0);
    const resolvedQubitCount = clamp(Math.max(metadata.qubit_count, referencedQubit + 1), 1, 24);

    const importedOperations = metadata.operations
      .filter((operation) => supportedGateValues.has(operation.gate))
      .filter((operation) => operation.target < resolvedQubitCount)
      .filter((operation) => operation.control == null || operation.control < resolvedQubitCount)
      .filter((operation) => !gateNeedsControl(operation.gate) || operation.control != null)
      .map((operation) => ({
        id: nextOperationId(),
        gate: operation.gate,
        target: operation.target,
        control: operation.control,
        parameter: operation.parameter,
      }));

    const importedPreset = isNoisePreset(metadata.noise_config.preset) ? metadata.noise_config.preset : "medium";
    const defaultNoiseLevel = importedPreset === "custom" ? 0.5 : noisePresetLevel(importedPreset);
    const importedNoiseChannels: Partial<Record<CircuitNoiseChannelKey, CircuitNoiseChannelConfig>> = {};
    noiseOptionsForHardwareTarget(resolvedTarget).forEach((option) => {
      const importedChannel = metadata.noise_config.channels[option.key];
      importedNoiseChannels[option.key] = {
        enabled: importedChannel?.enabled ?? true,
        level: clamp(importedChannel?.level ?? defaultNoiseLevel, 0, 1),
      };
    });

    const fallbackGate = gateOptionsForHardwareTarget(resolvedTarget)[0]?.value ?? "h";
    const suggestedGate = importedOperations[0]?.gate;
    const selectedImportedGate =
      suggestedGate && supportedGateValues.has(suggestedGate) ? suggestedGate : fallbackGate;

    const firstOperation = importedOperations[0];
    const firstParameterizedOperation = importedOperations.find((operation) => operation.parameter != null);

    setCircuitName(metadata.circuit_name.trim() || "custom_design");
    setHardwareTarget(resolvedTarget);
    setQubitCount(resolvedQubitCount);
    setOperations(importedOperations);
    setSelectedGate(selectedImportedGate);
    setTargetQubit(Math.min(firstOperation?.target ?? 0, resolvedQubitCount - 1));
    setControlQubit(
      Math.min(
        firstOperation?.control ?? (resolvedQubitCount > 1 ? 1 : 0),
        Math.max(0, resolvedQubitCount - 1),
      ),
    );
    setParameterInput(
      firstParameterizedOperation?.parameter != null ? `${firstParameterizedOperation.parameter}` : "1.5708",
    );
    setNoisePreset(importedPreset);
    setNoiseChannels(importedNoiseChannels);
    setPhotonicDetectorModel(metadata.photonic_detector_model);
    setCalibrationSnapshotId(metadata.calibration_snapshot_id ?? "");
    setErrorMessage(null);
  };

  const handleOpenPngImportDialog = () => {
    importPngInputRef.current?.click();
  };

  const handleImportCircuitPreviewPng = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    try {
      const metadata = await readCircuitMetadataFromPngFile(file);
      applyImportedCircuitMetadata(metadata);
    } catch {
      setErrorMessage("Could not import circuit from PNG. Use a PNG exported from this circuit preview.");
    }
  };

  const handleDownloadCircuitPreview = async () => {
    try {
      await exportCircuitPreviewPng({
        circuitName,
        providerFamily,
        hardwareTarget,
        qubitCount,
        operations,
        noisePreset,
        noiseChannels,
        photonicDetectorModel,
        calibrationSnapshotId,
      });
      setErrorMessage(null);
    } catch {
      setErrorMessage("Unable to export circuit preview as PNG.");
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal session-launcher-dialog circuit-design-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">Circuit Design</div>
            <div className="modal-subtitle">Provider: {providerName}</div>
          </div>
          <button className="modal-close" onClick={onClose} disabled={pending}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="session-launcher-dialog-copy">
            Build the circuit before launch. This design is attached to the session configuration and execution context.
          </p>

          <div className="circuit-design-grid">
            <div className="session-launcher-field">
              <label>Circuit Name</label>
              <input
                type="text"
                className="form-input"
                value={circuitName}
                onChange={(event) => setCircuitName(event.target.value)}
                placeholder="e.g. ghz_3q_custom"
                disabled={pending}
              />
            </div>
            <div className="session-launcher-field">
              <label>Qubits</label>
              <input
                type="number"
                className="form-input"
                value={qubitCount}
                min={1}
                max={24}
                onChange={(event) => {
                  const parsed = Number.parseInt(event.target.value, 10);
                  if (!Number.isFinite(parsed)) {
                    return;
                  }
                  const bounded = Math.max(1, Math.min(24, parsed));
                  setQubitCount(bounded);
                  setTargetQubit((current) => Math.min(current, bounded - 1));
                  setControlQubit((current) => Math.min(current, bounded - 1));
                }}
                disabled={pending}
              />
            </div>
            <div className="session-launcher-field">
              <label>Hardware Target</label>
              {hardwareTargets.length > 1 ? (
                <select
                  className="form-select"
                  value={hardwareTarget}
                  onChange={(event) => setHardwareTarget(event.target.value as CircuitHardwareTarget)}
                  disabled={pending}
                >
                  {hardwareTargets.map((target) => (
                    <option key={`hardware-target-${target}`} value={target}>
                      {hardwareTargetLabel(target)}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  className="form-input"
                  value={hardwareTargetLabel(hardwareTarget)}
                  readOnly
                  disabled
                />
              )}
            </div>
            <div className="session-launcher-field">
              <label>Calibration Snapshot</label>
              <select
                className="form-select"
                value={calibrationSnapshotId}
                onChange={(event) => setCalibrationSnapshotId(event.target.value)}
                disabled={pending || calibrationOptions.length === 0}
              >
                {calibrationOptions.length === 0 ? <option value="">No snapshot available</option> : null}
                {calibrationOptions.map((snapshot) => (
                  <option key={`calibration-${snapshot.id}`} value={snapshot.id}>
                    {snapshot.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="circuit-gate-builder">
            <div className="session-launcher-field">
              <label>Gate</label>
              <select
                className="form-select"
                value={selectedGate}
                onChange={(event) => setSelectedGate(event.target.value as CircuitGate)}
                disabled={pending}
              >
                {availableGates.map((gate) => (
                  <option key={`gate-option-${gate.value}`} value={gate.value}>
                    {gate.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="session-launcher-field">
              <label>Target Qubit</label>
              <select
                className="form-select"
                value={targetQubit}
                onChange={(event) => setTargetQubit(Number.parseInt(event.target.value, 10))}
                disabled={pending}
              >
                {qubitOptions.map((qubit) => (
                  <option key={`target-${qubit}`} value={qubit}>
                    q[{qubit}]
                  </option>
                ))}
              </select>
            </div>
            {gateNeedsControl(selectedGate) ? (
              <div className="session-launcher-field">
                <label>Control Qubit</label>
                <select
                  className="form-select"
                  value={controlQubit}
                  onChange={(event) => setControlQubit(Number.parseInt(event.target.value, 10))}
                  disabled={pending}
                >
                  {qubitOptions.map((qubit) => (
                    <option key={`control-${qubit}`} value={qubit}>
                      q[{qubit}]
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {gateNeedsParameter(selectedGate) ? (
              <div className="session-launcher-field">
                <label>Parameter (radians)</label>
                <input
                  type="text"
                  className="form-input"
                  value={parameterInput}
                  onChange={(event) => setParameterInput(event.target.value)}
                  disabled={pending}
                />
              </div>
            ) : null}
            <div className="circuit-builder-action">
              <button className="btn btn-secondary circuit-add-op-btn" onClick={addOperation} disabled={pending}>
                <Plus size={14} aria-hidden="true" />
                <span>Add Gate</span>
              </button>
            </div>
          </div>

          <div className="circuit-noise-section">
            <div className="circuit-noise-head">
              <span>Noise Injection</span>
              <span>{hardwareTargetLabel(hardwareTarget)} profile</span>
            </div>
            <div className="session-launcher-field">
              <label>Preset</label>
              <select
                className="form-select"
                value={noisePreset}
                onChange={(event) => applyNoisePreset(event.target.value as CircuitNoisePreset)}
                disabled={pending}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            {hardwareTarget === "photonic" ? (
              <div className="session-launcher-field">
                <label>Detector Model</label>
                <select
                  className="form-select"
                  value={photonicDetectorModel}
                  onChange={(event) => setPhotonicDetectorModel(event.target.value as PhotonicDetectorModel)}
                  disabled={pending}
                >
                  <option value="threshold">Threshold</option>
                  <option value="pnr_approx">PNR Approximation</option>
                </select>
              </div>
            ) : null}
            <div className="circuit-noise-list">
              {noiseOptions.map((option) => {
                const channel = noiseChannels[option.key] ?? { enabled: true, level: 0.5 };
                return (
                  <div key={`noise-${option.key}`} className="circuit-noise-row">
                    <label className="circuit-noise-label">
                      <input
                        type="checkbox"
                        checked={channel.enabled}
                        onChange={() => toggleNoiseChannel(option.key)}
                        disabled={pending}
                      />
                      <span>{option.label}</span>
                    </label>
                    <div className="circuit-noise-slider">
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={channel.level}
                        onChange={(event) => setNoiseChannelLevel(option.key, Number.parseFloat(event.target.value))}
                        disabled={pending || !channel.enabled}
                      />
                      <span>{channel.level.toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="circuit-compile-section">
            <div className="circuit-compile-head">
              <span>Hardware Compile Report</span>
              <span>{compileReport.profileLabel}</span>
            </div>
            <div className="circuit-compile-band">
              <span>Expected Fidelity Band</span>
              <strong>{compileReport.fidelityBand}</strong>
            </div>
            <div className="circuit-compile-metrics">
              {compileReport.metrics.map((metric) => (
                <div key={`compile-metric-${metric.label}`} className="circuit-compile-metric">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                </div>
              ))}
            </div>
            {compileReport.warnings.length > 0 ? (
              <div className="circuit-compile-warnings">
                {compileReport.warnings.map((warning) => (
                  <div key={`compile-warning-${warning}`} className="circuit-compile-warning">
                    {warning}
                  </div>
                ))}
              </div>
            ) : (
              <div className="scientific-muted-note">No compile warnings for the selected hardware target.</div>
            )}
            <div className="circuit-compile-syndrome">
              <span>{`Syndrome Preview: rounds≈${compileArtifact.syndrome_preview.rounds_est}`}</span>
              <span>{`stabilizers≈${compileArtifact.syndrome_preview.stabilizer_count_est}`}</span>
            </div>
          </div>

          <div className="circuit-ops-head">
            <span>Gate Sequence ({operations.length})</span>
            <span>Estimated Depth: {estimatedDepth}</span>
          </div>
          <div className="circuit-ops-list">
            {operations.length === 0 ? (
              <div className="scientific-muted-note">No gates added yet.</div>
            ) : (
              operations.map((operation, index) => (
                <div key={operation.id} className="circuit-op-row">
                  <span className="circuit-op-index">{index + 1}.</span>
                  <code className="circuit-op-code">{formatOperation(operation)}</code>
                  <div className="circuit-op-actions">
                    <button
                      className="btn-icon"
                      onClick={() => moveOperation(operation.id, "up")}
                      disabled={pending || index === 0}
                      title="Move up"
                    >
                      <ArrowUp size={14} aria-hidden="true" />
                    </button>
                    <button
                      className="btn-icon"
                      onClick={() => moveOperation(operation.id, "down")}
                      disabled={pending || index === operations.length - 1}
                      title="Move down"
                    >
                      <ArrowDown size={14} aria-hidden="true" />
                    </button>
                    <button
                      className="btn-icon"
                      onClick={() => removeOperation(operation.id)}
                      disabled={pending}
                      title="Remove gate"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="circuit-preview-head">
            <span>Circuit Preview</span>
            <div className="circuit-preview-head-actions">
              <span>{operations.length === 0 ? "Awaiting gates" : `${operations.length} registered`}</span>
              <input
                ref={importPngInputRef}
                type="file"
                accept="image/png"
                className="circuit-preview-import-input"
                onChange={handleImportCircuitPreviewPng}
              />
              <button
                className="btn-icon circuit-preview-download-btn"
                onClick={handleOpenPngImportDialog}
                disabled={pending}
                title="Upload PNG"
                aria-label="Upload circuit preview PNG"
              >
                <Upload size={14} aria-hidden="true" />
              </button>
              <button
                className="btn-icon circuit-preview-download-btn"
                onClick={handleDownloadCircuitPreview}
                disabled={pending}
                title="Download PNG"
                aria-label="Download circuit preview PNG"
              >
                <Download size={14} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className="circuit-preview-shell">
            <div className="circuit-preview-grid circuit-preview-grid-header" style={{ gridTemplateColumns: previewGridTemplate }}>
              <div className="circuit-preview-grid-anchor" />
              <div className="circuit-preview-grid-anchor" />
              {Array.from({ length: previewStepCount }, (_, stepIndex) => (
                <div key={`preview-step-${stepIndex}`} className="circuit-preview-step-label">
                  {operations.length === 0 ? "—" : `t${stepIndex + 1}`}
                </div>
              ))}
              <div className="circuit-preview-grid-anchor" />
            </div>
            <div className="circuit-preview-grid" style={{ gridTemplateColumns: previewGridTemplate }}>
              {qubitOptions.map((qubit) => (
                <Fragment key={`preview-row-${qubit}`}>
                  <div className="circuit-preview-start-state">|0⟩</div>
                  <div className="circuit-preview-qubit-label">{`q[${qubit}]`}</div>
                  {Array.from({ length: previewStepCount }, (_, stepIndex) => {
                    const operation = operations[stepIndex];
                    const cell = previewCellForOperation(operation, qubit);
                    return (
                      <div
                        key={`preview-cell-${qubit}-${stepIndex}`}
                        className={`circuit-preview-cell${cell.hasConnector ? " has-connector" : ""}`}
                        title={operation ? formatOperation(operation) : "No gate"}
                      >
                        {cell.kind === "control" ? <span className="circuit-preview-control-dot" aria-hidden="true" /> : null}
                        {cell.label ? (
                          <span className={`circuit-preview-gate-chip ${cell.kind}`}>{cell.label}</span>
                        ) : null}
                      </div>
                    );
                  })}
                  {(() => {
                    const intended = intendedEndStateByQubit.get(qubit);
                    if (intended) {
                      return (
                        <div
                          className="circuit-preview-end-state measured"
                          title={`Intended result: ${intended.intendedBit} (P(0) ${(intended.probabilityZero * 100).toFixed(1)}%, P(1) ${(intended.probabilityOne * 100).toFixed(1)}%)`}
                        >
                          {`|${intended.intendedBit}⟩`}
                        </div>
                      );
                    }
                    return (
                      <div className="circuit-preview-end-state">
                        {touchedQubits.has(qubit) ? "|ψ⟩" : "|0⟩"}
                      </div>
                    );
                  })()}
                </Fragment>
              ))}
            </div>
          </div>

          <div className="circuit-results-section">
            <div className="circuit-results-head">
              <span>Intended Measurement Results</span>
              <span>{measurementPreview.modelLabel}</span>
            </div>
            <div className="circuit-results-warning">{measurementPreview.warning}</div>
            {measurementPreview.unavailableReason ? (
              <div className="scientific-muted-note">{measurementPreview.unavailableReason}</div>
            ) : (
              <div className="circuit-results-list">
                {measurementPreview.rows.map((row) => (
                  <div key={`expected-${row.label}`} className="circuit-results-row">
                    <div className="circuit-results-label">{row.label}</div>
                    <div className="circuit-results-probabilities">
                      <span>P(0) {(row.probabilityZero * 100).toFixed(1)}%</span>
                      <span>P(1) {(row.probabilityOne * 100).toFixed(1)}%</span>
                    </div>
                    <div className="circuit-results-bit">Intended: {row.intendedBit}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="session-launcher-field">
            <label>{hardwareTarget === "superconducting" ? "OpenQASM Preview" : "Program Preview"}</label>
            <textarea className="form-textarea circuit-qasm-preview" value={qasmPreview} readOnly spellCheck={false} />
          </div>
          <div className="session-launcher-field">
            <label>Compile Artifact (JSON)</label>
            <textarea className="form-textarea circuit-compile-json" value={compileArtifactJson} readOnly spellCheck={false} />
          </div>
          {errorMessage ? <div className="session-launcher-error">{errorMessage}</div> : null}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleStart} disabled={pending}>
            {pending ? "Starting..." : "Start Session With Circuit"}
          </button>
        </div>
      </div>
    </div>
  );
}
