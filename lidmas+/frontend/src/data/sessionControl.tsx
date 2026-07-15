import { createContext, useContext, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";

export type SessionLaunchMode = "scientific" | "benchmark" | "replay";
export type SessionLaunchStatus = "idle" | "launching" | "running" | "stopping" | "failed";

export interface SessionControlState {
  activeRunId: string | null;
  activeSessionId: string | null;
  mode: SessionLaunchMode | null;
  status: SessionLaunchStatus;
  lastError: string | null;
}

interface SessionControlContextValue {
  state: SessionControlState;
  beginLaunch: (mode: SessionLaunchMode) => void;
  markRunning: (input: { runId: string; sessionId: string; mode: SessionLaunchMode }) => void;
  markStopping: () => void;
  markStopped: (options?: { preserveRun?: boolean }) => void;
  markFailed: (message: string) => void;
  setActiveContext: (input: { runId: string | null; sessionId: string | null; mode?: SessionLaunchMode | null }) => void;
  clearError: () => void;
}

const SessionControlContext = createContext<SessionControlContextValue | null>(null);

const initialState: SessionControlState = {
  activeRunId: null,
  activeSessionId: null,
  mode: null,
  status: "idle",
  lastError: null,
};

export function SessionControlProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<SessionControlState>(initialState);

  const value = useMemo<SessionControlContextValue>(
    () => ({
      state,
      beginLaunch: (mode) => {
        setState((current) => ({
          ...current,
          mode,
          status: "launching",
          lastError: null,
        }));
      },
      markRunning: ({ runId, sessionId, mode }) => {
        setState({
          activeRunId: runId,
          activeSessionId: sessionId,
          mode,
          status: "running",
          lastError: null,
        });
      },
      markStopping: () => {
        setState((current) => ({
          ...current,
          status: "stopping",
          lastError: null,
        }));
      },
      markStopped: (options) => {
        setState((current) => ({
          activeRunId: options?.preserveRun ? current.activeRunId : null,
          activeSessionId: null,
          mode: options?.preserveRun ? current.mode : null,
          status: "idle",
          lastError: null,
        }));
      },
      markFailed: (message) => {
        setState((current) => ({
          ...current,
          status: "failed",
          lastError: message,
        }));
      },
      setActiveContext: ({ runId, sessionId, mode }) => {
        setState((current) => ({
          activeRunId: runId,
          activeSessionId: sessionId,
          mode: mode === undefined ? current.mode : mode,
          status: sessionId ? "running" : current.status === "launching" ? "launching" : "idle",
          lastError: null,
        }));
      },
      clearError: () => {
        setState((current) => ({
          ...current,
          status: current.activeSessionId ? current.status : "idle",
          lastError: null,
        }));
      },
    }),
    [state],
  );

  return <SessionControlContext.Provider value={value}>{children}</SessionControlContext.Provider>;
}

export function useSessionControl() {
  const context = useContext(SessionControlContext);
  if (!context) {
    throw new Error("useSessionControl must be used inside SessionControlProvider");
  }
  return context;
}
