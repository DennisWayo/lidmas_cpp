# hardware_integration

This example converts Xanadu datasets to LiDMaS+ `decoder_io` NDJSON.
The same converter now supports:

- legacy Xanadu job JSON payloads,
- Aurora decoder-demo switch-setting directories,
- QCA/Borealis-style shot matrices (`samples.npy`),
- count-compressed outcomes (useful for GKP-style exports).

## Files

- `convert_xanadu_job_to_decoder_io.py`: converter script.
- `xanadu_job_result_example.json`: minimal sample job payload.
- `xanadu_syndrome_mapping_example.json`: mode-to-syndrome parity mapping.
- `aurora_batch_example/`: tiny Aurora-style batch with `switch_settings_qpu_*.json`.
- `xanadu_aurora_mapping_example.json`: Aurora mapping.
- `xanadu_qca_samples_example.json`: QCA-like shot-matrix fixture.
- `xanadu_qca_mapping_example.json`: QCA mapping.
- `xanadu_gkp_counts_example.json`: count-compressed outcome fixture.
- `xanadu_gkp_mapping_example.json`: GKP mapping.
- `run.sh`: one-command local demo.
- `run_aurora.sh`: Aurora conversion demo.
- `run_qca.sh`: QCA conversion demo.
- `run_gkp.sh`: GKP count-table conversion demo.
- `run_public_datasets.sh`: run Aurora + QCA + GKP demos.
- `replay.sh`: decode generated requests via `./build/lidmas --decoder_io_replay`.

## Quick Run

```bash
bash examples/hardware_integration/run.sh
```

Output:

- `examples/results/hardware_integration/decoder_requests.ndjson`

Each NDJSON line is a `DecodeRequest` compatible with `schemas/decoder_io.proto`.

Run all public-dataset fixtures:

```bash
bash examples/hardware_integration/run_public_datasets.sh
```

Outputs:

- `examples/results/hardware_integration/decoder_requests_aurora.ndjson`
- `examples/results/hardware_integration/decoder_requests_qca.ndjson`
- `examples/results/hardware_integration/decoder_requests_gkp.ndjson`

Replay those requests through the C++ adapter:

```bash
./build/lidmas --decoder_io_replay \
  --decoder_io_in=examples/results/hardware_integration/decoder_requests.ndjson \
  --decoder_io_out=examples/results/hardware_integration/decoder_responses.ndjson \
  --decoder_io_config=schemas/surface_decoder_adapter_config.json \
  --decoder_io_continue_on_error
```

Helper script (auto-derives response filename):

```bash
bash examples/hardware_integration/replay.sh \
  examples/results/hardware_integration/decoder_requests_aurora.ndjson
```

## Real Xanadu Job Data

### Aurora decoder_demo batch (switch settings)

Requires NumPy when reading `.npy` files:

```bash
python3 -m pip install numpy
```

Convert one Aurora batch directory:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format aurora_switch_dir \
  --input /path/to/decoder_demo/signal/batch_0 \
  --mapping examples/hardware_integration/xanadu_aurora_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_aurora.ndjson \
  --aurora-binarize \
  --max-shots 20000 \
  --meta hardware=xanadu \
  --meta dataset=aurora_decoder_demo
```

For large Aurora batches, enable streaming and progress logs:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format aurora_switch_dir \
  --stream \
  --input /path/to/decoder_demo/signal/batch_0 \
  --mapping examples/hardware_integration/xanadu_aurora_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_aurora.ndjson \
  --aurora-binarize \
  --max-shots 200000 \
  --progress-every 50000
```

### QCA / Borealis samples.npy

Convert `samples.npy` (shape typically `n x 1 x M`):

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --max-shots 50000 \
  --meta hardware=xanadu \
  --meta dataset=qca
```

Chunked QCA conversion (memory-safe over very large files):

```bash
# chunk 1
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --shot-start 0 \
  --max-shots 200000 \
  --progress-every 50000

# chunk 2 (append)
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --append-out \
  --shot-start 200000 \
  --max-shots 200000 \
  --progress-every 50000
```

### GKP outcome counts

For count-compressed outcomes exported from your analysis notebook:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format count_table_json \
  --input /path/to/gkp_outcome_counts.json \
  --mapping examples/hardware_integration/xanadu_gkp_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_gkp.ndjson \
  --max-shots 100000 \
  --meta hardware=xanadu \
  --meta dataset=gkp
```

`gkp_outcome_counts.json` entries should look like:

```json
{"counts":[{"sample":[0,1,0],"count":12},{"sample":[1,0,1],"count":5}]}
```

### Legacy Xanadu job JSON

Use the converter with exported job JSON payloads:

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

## Large-Data Flags

- `--stream`: uses NumPy memory-mapped loading when available (`.npy`), avoiding full in-memory expansion.
- `--shot-start N`: skip the first `N` expanded shots before writing.
- `--max-shots K`: write at most `K` shots this run.
- `--append-out`: append NDJSON to an existing output file.
- `--progress-every M`: emit progress every `M` written shots to stderr.
