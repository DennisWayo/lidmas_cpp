import { FlaskConical, Gauge, History } from "lucide-react";
import type { ReactNode } from "react";
import type { ProviderKind, ProviderStatus } from "../../api/types";

interface SessionLauncherMenuProps {
  open: boolean;
  providerOptions: Array<{ id: string; name: string; status: ProviderStatus; kind: ProviderKind }>;
  selectedProviderId: string;
  onSelectProvider: (providerId: string) => void;
  onStartScientific: () => void;
  onStartBenchmark: () => void;
  onStartReplay: () => void;
  scientificDisabledReason?: string | null;
  benchmarkDisabledReason?: string | null;
  replayDisabledReason?: string | null;
}

function providerStatusLabel(status: ProviderStatus): string {
  if (status === "ready") {
    return "ready";
  }
  if (status === "degraded") {
    return "degraded";
  }
  return "offline";
}

interface MenuActionProps {
  icon: ReactNode;
  title: string;
  detail: string;
  disabledReason?: string | null;
  onClick: () => void;
}

function MenuAction({ icon, title, detail, disabledReason, onClick }: MenuActionProps) {
  const disabled = Boolean(disabledReason);
  return (
    <button className="session-launcher-menu-item" disabled={disabled} onClick={onClick}>
      <span className="session-launcher-menu-icon">{icon}</span>
      <span className="session-launcher-menu-copy">
        <strong>{title}</strong>
        <span>{disabled ? disabledReason : detail}</span>
      </span>
    </button>
  );
}

export function SessionLauncherMenu({
  open,
  providerOptions,
  selectedProviderId,
  onSelectProvider,
  onStartScientific,
  onStartBenchmark,
  onStartReplay,
  scientificDisabledReason,
  benchmarkDisabledReason,
  replayDisabledReason,
}: SessionLauncherMenuProps) {
  if (!open) {
    return null;
  }

  const hardwareProviders = providerOptions.filter((provider) => provider.kind !== "simulated");
  const simulatorProviders = providerOptions.filter((provider) => provider.kind === "simulated");

  return (
    <div className="session-launcher-menu" role="menu" aria-label="Session launcher menu">
      <div className="session-launcher-menu-provider">
        <label>Launch Provider</label>
        <select
          className="select-field research-select"
          value={providerOptions.length === 0 ? "" : selectedProviderId}
          onChange={(event) => onSelectProvider(event.target.value)}
        >
          {providerOptions.length === 0 ? <option value="">No providers available</option> : null}
          {hardwareProviders.length > 0 ? (
            <optgroup label="Hardware Data">
              {hardwareProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} · {providerStatusLabel(provider.status)}
                </option>
              ))}
            </optgroup>
          ) : null}
          {simulatorProviders.length > 0 ? (
            <optgroup label="Simulators">
              {simulatorProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} · {providerStatusLabel(provider.status)}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </div>
      <MenuAction
        icon={<FlaskConical size={14} aria-hidden="true" />}
        title="Start Scientific Session"
        detail="Run exact decoder telemetry for scientific state updates."
        disabledReason={scientificDisabledReason}
        onClick={onStartScientific}
      />
      <MenuAction
        icon={<Gauge size={14} aria-hidden="true" />}
        title="Start Benchmark Session"
        detail="Configure multi-decoder comparison under one input scope."
        disabledReason={benchmarkDisabledReason}
        onClick={onStartBenchmark}
      />
      <MenuAction
        icon={<History size={14} aria-hidden="true" />}
        title="Start Replay Session"
        detail="Replay a historical run for deterministic rerun workflows."
        disabledReason={replayDisabledReason}
        onClick={onStartReplay}
      />
    </div>
  );
}
