export type CalibrationHardwareTarget = "superconducting" | "trapped_ion" | "photonic";
export type CalibrationProviderFamily = "xanadu" | "ankaa" | "ibm" | "pennylane" | "qiskit" | "cirq" | "unknown";
export type CalibrationVendor = "ibm" | "ankaa" | "xanadu" | "ionq";

export interface VendorCalibrationSnapshot {
  id: string;
  label: string;
  vendor: CalibrationVendor;
  hardwareTarget: CalibrationHardwareTarget;
  backend: string;
  capturedAt: string;
  source: string;
  metrics: Record<string, number>;
}

const SNAPSHOTS: VendorCalibrationSnapshot[] = [
  {
    id: "ibm_kingston_2026q2",
    label: "IBM Kingston (2026-Q2)",
    vendor: "ibm",
    hardwareTarget: "superconducting",
    backend: "ibm_kingston",
    capturedAt: "2026-04-21T10:20:30Z",
    source: "ibm_live_metadata_probe",
    metrics: {
      avg_1q_gate_error: 0.00092,
      avg_2q_gate_error: 0.0116,
      avg_readout_error: 0.0208,
      avg_t1_us: 91.2,
      avg_t2_us: 73.4,
      zz_coupling_khz: 18.1,
    },
  },
  {
    id: "ibm_torino_2026q1",
    label: "IBM Torino (2026-Q1)",
    vendor: "ibm",
    hardwareTarget: "superconducting",
    backend: "ibm_torino",
    capturedAt: "2026-02-02T08:13:40Z",
    source: "ibm_live_metadata_probe",
    metrics: {
      avg_1q_gate_error: 0.00106,
      avg_2q_gate_error: 0.0124,
      avg_readout_error: 0.0237,
      avg_t1_us: 84.7,
      avg_t2_us: 66.9,
      zz_coupling_khz: 20.4,
    },
  },
  {
    id: "ankaa_r3_2026q2",
    label: "Ankaa R3 Replay (2026-Q2)",
    vendor: "ankaa",
    hardwareTarget: "superconducting",
    backend: "ankaa_r3_replay",
    capturedAt: "2026-04-08T12:04:00Z",
    source: "ankaa_fixture_calibration",
    metrics: {
      avg_1q_gate_error: 0.00118,
      avg_2q_gate_error: 0.0141,
      avg_readout_error: 0.0279,
      avg_t1_us: 72.5,
      avg_t2_us: 58.3,
      zz_coupling_khz: 24.9,
    },
  },
  {
    id: "ionq_forte_2026q2",
    label: "IonQ Forte (2026-Q2)",
    vendor: "ionq",
    hardwareTarget: "trapped_ion",
    backend: "ionq_forte",
    capturedAt: "2026-03-18T15:06:00Z",
    source: "pennylane_hardware_profile",
    metrics: {
      avg_1q_gate_error: 0.00034,
      avg_ms_gate_error: 0.0036,
      avg_readout_error: 0.0122,
      avg_coherence_ms: 710.0,
      heating_quanta_per_ms: 0.083,
      addressing_crosstalk: 0.018,
    },
  },
  {
    id: "xanadu_aurora_2026q2",
    label: "Xanadu Aurora (2026-Q2)",
    vendor: "xanadu",
    hardwareTarget: "photonic",
    backend: "xanadu_aurora",
    capturedAt: "2026-04-09T11:20:00Z",
    source: "xanadu_remote_slice_calibration",
    metrics: {
      photon_loss_rate: 0.047,
      mode_mismatch: 0.019,
      phase_drift_deg: 2.4,
      detector_dark_count_rate: 0.0064,
      homodyne_efficiency: 0.937,
      non_gaussian_injection_failure: 0.031,
    },
  },
  {
    id: "xanadu_borealis_2026q1",
    label: "Xanadu Borealis (2026-Q1)",
    vendor: "xanadu",
    hardwareTarget: "photonic",
    backend: "xanadu_borealis",
    capturedAt: "2026-01-26T14:40:00Z",
    source: "xanadu_remote_slice_calibration",
    metrics: {
      photon_loss_rate: 0.053,
      mode_mismatch: 0.024,
      phase_drift_deg: 2.9,
      detector_dark_count_rate: 0.0078,
      homodyne_efficiency: 0.921,
      non_gaussian_injection_failure: 0.038,
    },
  },
];

function vendorsForContext(
  providerFamily: CalibrationProviderFamily,
  hardwareTarget: CalibrationHardwareTarget,
): CalibrationVendor[] {
  if (hardwareTarget === "trapped_ion") {
    return ["ionq"];
  }
  if (hardwareTarget === "photonic") {
    return ["xanadu"];
  }
  if (providerFamily === "ibm") {
    return ["ibm"];
  }
  if (providerFamily === "ankaa") {
    return ["ankaa"];
  }
  if (providerFamily === "qiskit" || providerFamily === "cirq") {
    return ["ibm", "ankaa"];
  }
  if (providerFamily === "pennylane") {
    return ["ibm", "ankaa"];
  }
  return ["ibm", "ankaa"];
}

export function calibrationSnapshotsForContext(
  providerFamily: CalibrationProviderFamily,
  hardwareTarget: CalibrationHardwareTarget,
  sourceSnapshots?: VendorCalibrationSnapshot[],
): VendorCalibrationSnapshot[] {
  const catalog = sourceSnapshots && sourceSnapshots.length > 0 ? sourceSnapshots : SNAPSHOTS;
  const vendors = new Set(vendorsForContext(providerFamily, hardwareTarget));
  return catalog.filter(
    (snapshot) => snapshot.hardwareTarget === hardwareTarget && vendors.has(snapshot.vendor),
  );
}

export function defaultCalibrationSnapshotId(
  providerFamily: CalibrationProviderFamily,
  hardwareTarget: CalibrationHardwareTarget,
  sourceSnapshots?: VendorCalibrationSnapshot[],
): string | null {
  const options = calibrationSnapshotsForContext(providerFamily, hardwareTarget, sourceSnapshots);
  if (options.length === 0) {
    return null;
  }
  if (hardwareTarget === "photonic") {
    return options.find((option) => option.id.includes("aurora"))?.id ?? options[0].id;
  }
  if (hardwareTarget === "trapped_ion") {
    return options[0].id;
  }
  if (providerFamily === "qiskit" || providerFamily === "cirq" || providerFamily === "ibm") {
    return options.find((option) => option.vendor === "ibm")?.id ?? options[0].id;
  }
  if (providerFamily === "ankaa") {
    return options.find((option) => option.vendor === "ankaa")?.id ?? options[0].id;
  }
  return options[0].id;
}

export function findCalibrationSnapshotById(id: string): VendorCalibrationSnapshot | null {
  const normalized = id.trim();
  if (!normalized) {
    return null;
  }
  return SNAPSHOTS.find((snapshot) => snapshot.id === normalized) ?? null;
}

function parseVendor(value: unknown): CalibrationVendor | null {
  if (value === "ibm" || value === "ankaa" || value === "xanadu" || value === "ionq") {
    return value;
  }
  return null;
}

function parseHardwareTarget(value: unknown): CalibrationHardwareTarget | null {
  if (value === "superconducting" || value === "trapped_ion" || value === "photonic") {
    return value;
  }
  return null;
}

export function normalizeVendorCalibrationSnapshots(payload: unknown): VendorCalibrationSnapshot[] {
  if (!Array.isArray(payload)) {
    return [];
  }
  const snapshots: VendorCalibrationSnapshot[] = [];
  payload.forEach((entry) => {
    if (!entry || typeof entry !== "object") {
      return;
    }
    const raw = entry as Record<string, unknown>;
    const id = typeof raw.id === "string" ? raw.id.trim() : "";
    const label = typeof raw.label === "string" ? raw.label.trim() : "";
    const vendor = parseVendor(raw.vendor);
    const hardwareTarget = parseHardwareTarget(raw.hardware_target ?? raw.hardwareTarget);
    const backend = typeof raw.backend === "string" ? raw.backend.trim() : "";
    const capturedAt = typeof raw.captured_at === "string"
      ? raw.captured_at
      : typeof raw.capturedAt === "string"
        ? raw.capturedAt
        : "";
    const source = typeof raw.source === "string" ? raw.source.trim() : "";
    const metricsRaw = raw.metrics;
    const metrics: Record<string, number> = {};
    if (metricsRaw && typeof metricsRaw === "object") {
      Object.entries(metricsRaw as Record<string, unknown>).forEach(([key, value]) => {
        const numeric = typeof value === "number" ? value : Number.NaN;
        if (Number.isFinite(numeric)) {
          metrics[key] = numeric;
        }
      });
    }
    if (!id || !label || !vendor || !hardwareTarget || !backend || !capturedAt || !source) {
      return;
    }
    snapshots.push({
      id,
      label,
      vendor,
      hardwareTarget,
      backend,
      capturedAt,
      source,
      metrics,
    });
  });
  return snapshots;
}
