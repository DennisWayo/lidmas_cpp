import { SCIENTIFIC_FIELD_LABELS } from "./contracts";
import { type ScientificStateResult } from "./stateMachine";

interface ScientificCompletenessPanelProps {
  result: ScientificStateResult;
}

function labelsForSignals(signals: Array<keyof typeof SCIENTIFIC_FIELD_LABELS>): string {
  if (signals.length === 0) {
    return "none";
  }
  return signals.map((signal) => SCIENTIFIC_FIELD_LABELS[signal]).join(", ");
}

export function ScientificCompletenessPanel({ result }: ScientificCompletenessPanelProps) {
  const { completeness, integrityIssues } = result;
  const impact = completeness.impactSummary.slice(0, 3);

  return (
    <div className="scientific-completeness-panel">
      <div className="scientific-completeness-row">
        <span>Scientific state</span>
        <strong>{result.state}</strong>
      </div>
      <div className="scientific-completeness-row">
        <span>Completeness</span>
        <strong>{completeness.percentage}%</strong>
      </div>
      <div className="scientific-completeness-row">
        <span>Exact signals</span>
        <strong>{labelsForSignals(completeness.availableSignals)}</strong>
      </div>
      <div className="scientific-completeness-row">
        <span>Missing signals</span>
        <strong>{labelsForSignals(completeness.missingSignals)}</strong>
      </div>
      <div className="scientific-completeness-row">
        <span>Integrity warnings</span>
        <strong>{integrityIssues.length === 0 ? "none" : integrityIssues.map((issue) => issue.code).join(", ")}</strong>
      </div>
      <div className="scientific-completeness-impact">
        <span>Impact</span>
        {impact.map((line) => (
          <strong key={line}>{line}</strong>
        ))}
      </div>
    </div>
  );
}
