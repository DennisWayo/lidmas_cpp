import { ChevronDown, ChevronUp, Square } from "lucide-react";
import type { ProviderKind, ProviderStatus } from "../../api/types";
import { type SessionLaunchStatus } from "../../data/sessionControl";
import { SessionLauncherMenu } from "./SessionLauncherMenu";

interface SessionLauncherButtonProps {
  launchStatus: SessionLaunchStatus;
  isMenuOpen: boolean;
  providerOptions: Array<{ id: string; name: string; status: ProviderStatus; kind: ProviderKind }>;
  selectedProviderId: string;
  onSelectProvider: (providerId: string) => void;
  onToggleMenu: () => void;
  onStartScientific: () => void;
  onOpenBenchmark: () => void;
  onOpenReplay: () => void;
  onStopSession: () => void;
  onViewRun: () => void;
  canViewRun: boolean;
  scientificDisabledReason?: string | null;
  benchmarkDisabledReason?: string | null;
  replayDisabledReason?: string | null;
  showIngestingChip?: boolean;
}

export function SessionLauncherButton({
  launchStatus,
  isMenuOpen,
  providerOptions,
  selectedProviderId,
  onSelectProvider,
  onToggleMenu,
  onStartScientific,
  onOpenBenchmark,
  onOpenReplay,
  onStopSession,
  onViewRun,
  canViewRun,
  scientificDisabledReason,
  benchmarkDisabledReason,
  replayDisabledReason,
  showIngestingChip = false,
}: SessionLauncherButtonProps) {
  const starting = launchStatus === "launching";
  const stopping = launchStatus === "stopping";
  const running = launchStatus === "running";
  const scientificDisabled = Boolean(scientificDisabledReason);

  if (running || stopping) {
    return (
      <div className="session-launcher-inline">
        <button className="btn btn-status-failed decoder-inline-btn" onClick={onStopSession} disabled={stopping}>
          <Square size={13} aria-hidden="true" />
          <span>{stopping ? "Stopping..." : "Stop Session"}</span>
        </button>
        <button className="btn btn-secondary decoder-inline-btn" onClick={onViewRun} disabled={!canViewRun}>
          <span>View Run</span>
        </button>
        {showIngestingChip ? (
          <span className="status-badge status-running session-launcher-chip">
            ● Session running — ingesting telemetry
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="session-launcher-inline">
      <div className="session-launcher-split">
        <button
          className="btn btn-primary decoder-inline-btn"
          onClick={onStartScientific}
          disabled={starting || scientificDisabled}
          title={scientificDisabledReason ?? undefined}
        >
          <span>{starting ? "Starting..." : "Start Session"}</span>
        </button>
        <button
          className="btn btn-primary session-launcher-toggle"
          onClick={onToggleMenu}
          disabled={starting}
          aria-haspopup="menu"
          aria-expanded={isMenuOpen}
          title="Open session launcher"
        >
          {isMenuOpen ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
        </button>
        <SessionLauncherMenu
          open={isMenuOpen}
          providerOptions={providerOptions}
          selectedProviderId={selectedProviderId}
          onSelectProvider={onSelectProvider}
          onStartScientific={onStartScientific}
          onStartBenchmark={onOpenBenchmark}
          onStartReplay={onOpenReplay}
          scientificDisabledReason={scientificDisabledReason}
          benchmarkDisabledReason={benchmarkDisabledReason}
          replayDisabledReason={replayDisabledReason}
        />
      </div>
    </div>
  );
}
