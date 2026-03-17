# hardware_integration

This example converts Xanadu-style job outputs to LiDMaS+ `decoder_io` NDJSON.

## Files

- `convert_xanadu_job_to_decoder_io.py`: converter script.
- `xanadu_job_result_example.json`: minimal sample job payload.
- `xanadu_syndrome_mapping_example.json`: mode-to-syndrome parity mapping.
- `run.sh`: one-command local demo.
- `replay.sh`: decode generated requests via `./build/lidmas --decoder_io_replay`.

## Quick Run

```bash
bash examples/hardware_integration/run.sh
```

Output:

- `examples/results/hardware_integration/decoder_requests.ndjson`

Each NDJSON line is a `DecodeRequest` compatible with `schemas/decoder_io.proto`.

Replay those requests through the C++ adapter:

```bash
./build/lidmas --decoder_io_replay \
  --decoder_io_in=examples/results/hardware_integration/decoder_requests.ndjson \
  --decoder_io_out=examples/results/hardware_integration/decoder_responses.ndjson \
  --decoder_io_config=schemas/surface_decoder_adapter_config.json \
  --decoder_io_continue_on_error
```

## Real Xanadu Job Data

Use the converter with your exported job JSON:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --input /path/to/xanadu_job.json \
  --mapping /path/to/your_mapping.json \
  --out examples/results/hardware_integration/decoder_requests.ndjson \
  --sigma 0.18 \
  --gate-error-rate 0.0007 \
  --meas-error-rate 0.0009 \
  --idle-error-rate 0.0003 \
  --meta hardware=xanadu \
  --meta backend=X8_01
```

## Mapping Notes

`stabilizers` entries define syndrome-event generation by parity:

- `index`: stabilizer index in LiDMaS+ space.
- `type`: `X`, `Z`, or `UNKNOWN`.
- `modes`: list of measured-mode indices used for parity.
- `mod`: modulus (default 2).
- `trigger_on`: event if `(sum(modes) % mod) == trigger_on` (default 1).
- `time_offset_ns`: optional per-stabilizer event timestamp offset.

This mapping is hardware- and experiment-specific.
Illustrative mappings may produce non-physical syndromes; use `--decoder_io_continue_on_error` during early integration.
