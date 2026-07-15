import type { DecoderKey } from "../../data/decoders";

interface StartBenchmarkSessionDialogProps {
  open: boolean;
  pending: boolean;
  decoderOptions: Array<{ key: DecoderKey; label: string }>;
  selectedDecoders: DecoderKey[];
  onToggleDecoder: (decoder: DecoderKey) => void;
  onClose: () => void;
  onStart: () => void;
  disabledReason?: string | null;
}

export function StartBenchmarkSessionDialog({
  open,
  pending,
  decoderOptions,
  selectedDecoders,
  onToggleDecoder,
  onClose,
  onStart,
  disabledReason,
}: StartBenchmarkSessionDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-small session-launcher-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Benchmark Decoder Policies</div>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="session-launcher-dialog-copy">
            Compare multiple decoders under identical provider scope and telemetry input.
          </p>
          <div className="session-launcher-checklist">
            {decoderOptions.map((decoder) => (
              <label key={decoder.key} className="session-launcher-checkrow">
                <input
                  type="checkbox"
                  checked={selectedDecoders.includes(decoder.key)}
                  onChange={() => onToggleDecoder(decoder.key)}
                />
                <span>{decoder.label}</span>
              </label>
            ))}
          </div>
          {disabledReason ? <div className="scientific-muted-note">{disabledReason}</div> : null}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={onStart} disabled={pending || Boolean(disabledReason)}>
            {pending ? "Starting..." : "Start Benchmark Session"}
          </button>
        </div>
      </div>
    </div>
  );
}
