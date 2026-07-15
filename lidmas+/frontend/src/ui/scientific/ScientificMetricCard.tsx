import { SCIENTIFIC_FIELD_LABELS, type ScientificCardContract } from "./contracts";
import {
  evaluateScientificMetricAvailability,
  type ScientificSignals,
  type ScientificStateResult,
} from "./stateMachine";

interface ScientificMetricCardProps {
  contract: ScientificCardContract;
  result: ScientificStateResult;
  value: string;
  hideWhenUnavailable?: boolean;
  forceVisible?: boolean;
  zeroBaseline?: boolean;
}

export function ScientificMetricCard({
  contract,
  result,
  value,
  hideWhenUnavailable = true,
  forceVisible = false,
  zeroBaseline = false,
}: ScientificMetricCardProps) {
  const availability = evaluateScientificMetricAvailability(
    contract,
    result.signals as ScientificSignals,
    result.hasRunContext,
    result.hasTelemetryContext,
  );

  if ((result.state === "IDLE" || result.state === "DEGRADED") && !forceVisible) {
    return null;
  }

  if (!availability.available) {
    if (zeroBaseline) {
      return (
        <div className="kpi-card">
          <div className="kpi-label">{contract.label}</div>
          <div className="kpi-value">{value}</div>
          <div className="kpi-trend">Awaiting job start</div>
        </div>
      );
    }
    if (hideWhenUnavailable) {
      return null;
    }
    return (
      <div className="kpi-card kpi-card-muted">
        <div className="kpi-label">{contract.label}</div>
        <div className="kpi-value scientific-kpi-placeholder">Blocked</div>
        <div className="kpi-trend">{availability.availabilityReason}</div>
      </div>
    );
  }

  if (!contract.stateEligibility.includes(result.state) && !forceVisible) {
    return null;
  }

  return (
    <div className="kpi-card">
      <div className="kpi-label">{contract.label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-trend">
        {contract.requiredFields.map((field) => SCIENTIFIC_FIELD_LABELS[field]).join(" / ")}
      </div>
    </div>
  );
}
