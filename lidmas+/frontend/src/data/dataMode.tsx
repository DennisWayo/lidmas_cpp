import { createContext, useContext, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { parseDecoderKey } from "./decoders";
import type { DecoderKey } from "./decoders";

export type DataMode = "api" | "mock";

interface DataModeContextValue {
  mode: DataMode;
  isApi: boolean;
  isMock: boolean;
  setMode: (mode: DataMode) => void;
  toggleMode: () => void;
  systemOff: boolean;
  setSystemOff: (off: boolean) => void;
  toggleSystemOff: () => void;
  systemArmed: boolean;
  armSystem: () => void;
  resetSystemArming: () => void;
  activeDecoder: DecoderKey;
  setActiveDecoder: (decoder: DecoderKey) => void;
  neuralModelPath: string;
  setNeuralModelPath: (path: string) => void;
}

const STORAGE_MODE_KEY = "lidmas.data_mode";
const STORAGE_DECODER_KEY = "lidmas.active_decoder";
const STORAGE_NEURAL_MODEL_KEY = "lidmas.neural_model_path";
const STORAGE_SYSTEM_OFF_KEY = "lidmas.system_off";
const STORAGE_SYSTEM_ARMED_KEY = "lidmas.system_armed";
const RUNTIME_QUERY_ROOTS = new Set([
  "health",
  "providers",
  "jobs",
  "runs",
  "run-telemetry",
  "paper-04-manifest",
  "integration-sessions",
  "integration-session-logs",
  "hardware-schema",
  "hardware-sessions",
]);

function parseMode(value: string | null | undefined): DataMode | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "api") {
    return "api";
  }
  if (normalized === "mock" || normalized === "gkp") {
    return "mock";
  }
  return null;
}

function getInitialMode(): DataMode {
  const envMode = parseMode(import.meta.env.VITE_DATA_MODE);
  if (typeof window === "undefined") {
    return envMode ?? "api";
  }

  const paramMode = parseMode(new URL(window.location.href).searchParams.get("data"));
  if (paramMode) {
    return paramMode;
  }

  const storedMode = parseMode(window.localStorage.getItem(STORAGE_MODE_KEY));
  return storedMode ?? envMode ?? "api";
}

function getInitialDecoder(): DecoderKey {
  const envDecoder = parseDecoderKey(import.meta.env.VITE_DEFAULT_DECODER);
  if (typeof window === "undefined") {
    return envDecoder ?? "mwpm";
  }

  const paramDecoder = parseDecoderKey(new URL(window.location.href).searchParams.get("decoder"));
  if (paramDecoder) {
    return paramDecoder;
  }

  const storedDecoder = parseDecoderKey(window.localStorage.getItem(STORAGE_DECODER_KEY));
  return storedDecoder ?? envDecoder ?? "mwpm";
}

function getInitialNeuralModelPath(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const paramValue = new URL(window.location.href).searchParams.get("neural_model");
  if (paramValue && paramValue.trim().length > 0) {
    return paramValue.trim();
  }

  const storedValue = window.localStorage.getItem(STORAGE_NEURAL_MODEL_KEY);
  if (!storedValue) {
    return "";
  }
  return storedValue.trim();
}

function getInitialSystemOff(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const raw = window.localStorage.getItem(STORAGE_SYSTEM_OFF_KEY);
  if (!raw) {
    return false;
  }
  const normalized = raw.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes" || normalized === "on";
}

function getInitialSystemArmed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const raw = window.localStorage.getItem(STORAGE_SYSTEM_ARMED_KEY);
  if (!raw) {
    return false;
  }
  const normalized = raw.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes" || normalized === "on";
}

const DataModeContext = createContext<DataModeContextValue | null>(null);

export function DataModeProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [mode, setModeState] = useState<DataMode>(getInitialMode);
  const [systemOff, setSystemOffState] = useState<boolean>(getInitialSystemOff);
  const [systemArmed, setSystemArmedState] = useState<boolean>(getInitialSystemArmed);
  const [activeDecoder, setActiveDecoderState] = useState<DecoderKey>(getInitialDecoder);
  const [neuralModelPath, setNeuralModelPathState] = useState<string>(getInitialNeuralModelPath);

  const setMode = (nextMode: DataMode) => {
    setModeState(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_MODE_KEY, nextMode);
    }
  };

  const setActiveDecoder = (nextDecoder: DecoderKey) => {
    setActiveDecoderState(nextDecoder);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_DECODER_KEY, nextDecoder);
    }
  };

  const setNeuralModelPath = (nextPath: string) => {
    setNeuralModelPathState(nextPath);
    if (typeof window !== "undefined") {
      const trimmed = nextPath.trim();
      if (trimmed) {
        window.localStorage.setItem(STORAGE_NEURAL_MODEL_KEY, trimmed);
      } else {
        window.localStorage.removeItem(STORAGE_NEURAL_MODEL_KEY);
      }
    }
  };

  const toggleMode = () => {
    setMode(mode === "api" ? "mock" : "api");
  };

  const clearRuntimeQueryCache = () => {
    void queryClient.cancelQueries({
      predicate: (query) => {
        const root = query.queryKey[0];
        return typeof root === "string" && RUNTIME_QUERY_ROOTS.has(root);
      },
    });
    queryClient.removeQueries({
      predicate: (query) => {
        const root = query.queryKey[0];
        return typeof root === "string" && RUNTIME_QUERY_ROOTS.has(root);
      },
    });
  };

  const resetSystemArming = () => {
    setSystemArmedState(false);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_SYSTEM_ARMED_KEY);
    }
  };

  const armSystem = () => {
    setSystemArmedState(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_SYSTEM_ARMED_KEY, "1");
    }
  };

  const setSystemOff = (off: boolean) => {
    setSystemOffState(off);
    if (typeof window !== "undefined") {
      if (off) {
        window.localStorage.setItem(STORAGE_SYSTEM_OFF_KEY, "1");
      } else {
        window.localStorage.removeItem(STORAGE_SYSTEM_OFF_KEY);
      }
    }
    if (off) {
      resetSystemArming();
      clearRuntimeQueryCache();
      return;
    }
    // Turning back on starts in standby until user selects provider and launches a run.
    resetSystemArming();
  };

  const toggleSystemOff = () => {
    setSystemOff(!systemOff);
  };

  const value = useMemo<DataModeContextValue>(
    () => ({
      mode,
      isApi: mode === "api",
      isMock: mode === "mock",
      setMode,
      toggleMode,
      systemOff,
      setSystemOff,
      toggleSystemOff,
      systemArmed,
      armSystem,
      resetSystemArming,
      activeDecoder,
      setActiveDecoder,
      neuralModelPath,
      setNeuralModelPath,
    }),
    [activeDecoder, mode, neuralModelPath, systemArmed, systemOff],
  );

  return <DataModeContext.Provider value={value}>{children}</DataModeContext.Provider>;
}

export function useDataMode() {
  const context = useContext(DataModeContext);
  if (!context) {
    throw new Error("useDataMode must be used inside DataModeProvider");
  }
  return context;
}
