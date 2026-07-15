import {
  scientificStateLabel,
  scientificStateStatusClass,
  type ScientificStateResult,
} from "./stateMachine";

interface ScientificStateBannerProps {
  result: ScientificStateResult;
}

function descriptionForState(state: ScientificStateResult["state"]): string {
  if (state === "IDLE") {
    return "No active run or telemetry context is selected.";
  }
  if (state === "INGESTING") {
    return "Telemetry is arriving; exact decoder contracts are still being satisfied.";
  }
  if (state === "PARTIAL") {
    return "Some exact contracts are satisfied while other scientific signals are still missing.";
  }
  if (state === "EXACT") {
    return "All required scientific contracts are satisfied and rates are contract-valid.";
  }
  if (state === "VALIDATED") {
    return "Exact scientific contracts are satisfied and validation checks have passed.";
  }
  return "Scientific integrity checks detected conflicts. Scientific rates are blocked.";
}

export function ScientificStateBanner({ result }: ScientificStateBannerProps) {
  return (
    <div className="scientific-state-banner">
      <div>
        <div className="scientific-state-title">{scientificStateLabel(result.state)}</div>
        <div className="scientific-state-description">{descriptionForState(result.state)}</div>
      </div>
      <span className={`status-badge ${scientificStateStatusClass(result.state)}`}>● {result.state}</span>
    </div>
  );
}
