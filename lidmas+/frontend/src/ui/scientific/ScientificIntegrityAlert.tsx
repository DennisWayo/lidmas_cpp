import type { ScientificIntegrityIssue } from "./contracts";

interface ScientificIntegrityAlertProps {
  issues: ScientificIntegrityIssue[];
}

export function ScientificIntegrityAlert({ issues }: ScientificIntegrityAlertProps) {
  if (issues.length === 0) {
    return null;
  }

  return (
    <div className="scientific-integrity-alert">
      <div className="scientific-integrity-title">Scientific integrity compromised</div>
      <div className="scientific-integrity-subtitle">
        Scientific rates are blocked until data-contract conflicts are resolved.
      </div>
      <div className="scientific-integrity-list">
        {issues.map((issue) => (
          <div key={issue.code} className="scientific-integrity-item">
            <strong>{issue.code}</strong>
            <span>{issue.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
