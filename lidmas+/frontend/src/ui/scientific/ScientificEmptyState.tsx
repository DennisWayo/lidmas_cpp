interface ScientificEmptyStateProps {
  onStartScientificSession?: () => void;
  onOpenSessionLauncher?: () => void;
  startDisabled?: boolean;
  startDisabledReason?: string | null;
  launcherDisabled?: boolean;
}

export function ScientificEmptyState({
  onStartScientificSession,
  onOpenSessionLauncher,
  startDisabled = false,
  startDisabledReason,
  launcherDisabled = false,
}: ScientificEmptyStateProps) {
  return (
    <div className="empty-card scientific-empty-state">
      <strong>No active scientific context</strong>
      <p>
        Select a run, start a decoder session, or replay a dataset to compute scientific metrics.
      </p>
      {(onStartScientificSession || onOpenSessionLauncher) ? (
        <div className="scientific-empty-actions">
          {onStartScientificSession ? (
            <button
              className="btn btn-primary"
              onClick={onStartScientificSession}
              disabled={startDisabled}
              title={startDisabledReason ?? undefined}
            >
              Start Scientific Session
            </button>
          ) : null}
          {onOpenSessionLauncher ? (
            <button className="btn btn-secondary" onClick={onOpenSessionLauncher} disabled={launcherDisabled}>
              Open Session Launcher
            </button>
          ) : null}
        </div>
      ) : null}
      {startDisabled && startDisabledReason ? <div className="scientific-muted-note">{startDisabledReason}</div> : null}
    </div>
  );
}
