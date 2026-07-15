export type DecoderKey = "mwpm" | "bp" | "neural_mwpm" | "uf";

export const DECODERS: Array<{ key: DecoderKey; label: string }> = [
  { key: "mwpm", label: "MWPM" },
  { key: "bp", label: "BP" },
  { key: "neural_mwpm", label: "Neural MWPM" },
  { key: "uf", label: "UF" },
];

export const DECODER_PROFILES: Record<
  DecoderKey,
  {
    noiseBias: number;
    successBias: number;
    latencyBias: number;
    waveScale: number;
  }
> = {
  mwpm: {
    noiseBias: -0.0008,
    successBias: 1.2,
    latencyBias: 3.4,
    waveScale: 1.0,
  },
  bp: {
    noiseBias: 0.0006,
    successBias: 0.4,
    latencyBias: -2.6,
    waveScale: 1.15,
  },
  neural_mwpm: {
    noiseBias: -0.0012,
    successBias: 1.7,
    latencyBias: -4.4,
    waveScale: 0.92,
  },
  uf: {
    noiseBias: 0.0011,
    successBias: -0.7,
    latencyBias: -1.2,
    waveScale: 1.25,
  },
};

export function parseDecoderKey(value: string | null | undefined): DecoderKey | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "mwpm" || normalized === "mwpm_gkp" || normalized === "mwpm-gkp") {
    return "mwpm";
  }
  if (normalized === "bp" || normalized === "bp_osd") {
    return "bp";
  }
  if (normalized === "neural_mwpm" || normalized === "neural-mwpm" || normalized === "neural") {
    return "neural_mwpm";
  }
  if (normalized === "uf" || normalized === "union_find" || normalized === "union-find") {
    return "uf";
  }
  return null;
}

export function decoderLabel(key: DecoderKey): string {
  return DECODERS.find((decoder) => decoder.key === key)?.label ?? key;
}

export function decoderMatchesKey(decoderName: string, key: DecoderKey): boolean {
  return parseDecoderKey(decoderName) === key;
}
