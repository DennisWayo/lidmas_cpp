# Hardware Integration

LiDMaS+ supports three data ingestion modes for hardware integration:

1. gRPC streaming (recommended)
2. File batch (NDJSON)
3. In-process C++ adapter API

Provider-specific examples live under `hardware_integration/<provider>/`.
Current provider directories:

- `hardware_integration/ankaa/superconducting/`
- `hardware_integration/ibm/superconducting/`
- `hardware_integration/xanadu/`

## Provider quick start

```bash
# Ankaa superconducting replay
bash hardware_integration/ankaa/superconducting/run_ankaa_stream.sh \
  --input hardware_integration/ankaa/superconducting/ankaa_fixture_example.json

# IBM superconducting live polling
export IBM_QUANTUM_API_KEY="<api-key>"
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh \
  --backend-name ibm_kingston \
  --poll-interval 30
```

## Recommended default

- Use **sparse time-stamped syndrome events** by default.
- Switch to dense bitsets when syndrome occupancy exceeds ~10–15%.

## Decoder IO schema (protobuf)

See `schemas/decoder_io.proto` for the canonical schema.

Key fields:

- `code_id`: string identifier for the code (e.g., `surface_d5`, `gkp_surface_d7`).
- `round_index`: integer round counter.
- `events`: sparse time-stamped syndrome events.
- `dense`: optional packed bitsets for dense syndromes.
- `noise`: supports sigma + gate/measurement/idle noise and per-qubit loss.
- `correction.qubit_flips_x` / `correction.qubit_flips_z`: optional per-type corrections when both X/Z syndromes are provided. `correction.qubit_flips` remains a union for backward compatibility.

## NDJSON file batch

Each line is one `DecodeRequest` JSON object.
See `schemas/decoder_io_example.ndjson` for examples.

### Ankaa superconducting replay stream

`hardware_integration/ankaa/superconducting/ankaa_qec_replay_stream.py` replays
archived Ankaa-style measurements into normalized stream frames.

Supported input formats:

- fixture JSON (`ankaa_fixture_example.json` style)
- HDF5 files with `hard_measurements` groups

Basic replay:

```bash
bash hardware_integration/ankaa/superconducting/run_ankaa_stream.sh \
  --input hardware_integration/ankaa/superconducting/ankaa_fixture_example.json \
  --max-rounds 12
```

Replay and push telemetry to LiDMaS+ backend:

```bash
bash hardware_integration/ankaa/superconducting/run_ankaa_stream.sh \
  --input /path/to/stability_8_without_resets_raw_data.h5 \
  --run-id <RUN_UUID> \
  --backend-base-url http://127.0.0.1:8080/api/v1
```

Install optional dependency automatically:

```bash
bash hardware_integration/ankaa/superconducting/run_ankaa_stream.sh \
  --install-deps \
  --input hardware_integration/ankaa/superconducting/ankaa_fixture_example.json
```

Outputs are written to:

- `examples/results/hardware_integration/ankaa/superconducting/`

### IBM superconducting live stream

`hardware_integration/ibm/superconducting/ibm_live_noise_stream.py` polls IBM
Quantum backend properties and emits normalized live frames.

Authentication note:

- LiDMaS+ UI does **not** ask for IBM API key.
- IBM auth is resolved on the machine running the adapter via either:
  - `IBM_QUANTUM_API_KEY` environment variable, or
  - previously saved `qiskit-ibm-runtime` account credentials.
- If neither is available, the session will fail and the error appears in adapter session logs.

Start IBM live polling:

```bash
export IBM_QUANTUM_API_KEY="<api-key>"
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh \
  --backend-name ibm_kingston \
  --poll-interval 30
```

Live polling with telemetry push:

```bash
export IBM_QUANTUM_API_KEY="<api-key>"
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh \
  --backend-name ibm_kingston \
  --run-id <RUN_UUID> \
  --backend-base-url http://127.0.0.1:8080/api/v1
```

Install optional IBM dependency automatically:

```bash
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh \
  --install-deps \
  --backend-name ibm_kingston
```

Outputs are written to:

- `examples/results/hardware_integration/ibm/superconducting/`

### Xanadu dataset conversion helper

Use the built-in converter example to transform Xanadu data into
`DecodeRequest` NDJSON.

Supported source modes:

- `xanadu_job_json`: legacy job payloads with `output`/`samples`.
- `aurora_switch_dir`: Aurora decoder-demo batch directory with
  `switch_settings_qpu_*.npy` (or `.json` in fixture mode).
- `shot_matrix`: generic shot arrays from `.json`, `.npy`, or `.npz`
  (covers QCA `samples.npy`).
- `count_table_json`: count-compressed outcomes (`sample` + `count`), useful for
  GKP-style exports.

Legacy job JSON:

```bash
python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format xanadu_job_json \
  --input /path/to/xanadu_job.json \
  --mapping /path/to/your_mapping.json \
  --out examples/results/hardware_integration/decoder_requests.ndjson
```

Quick demo:

```bash
bash hardware_integration/xanadu/run.sh
```

Aurora / QCA / GKP fixture demos:

```bash
bash hardware_integration/xanadu/run_public_datasets.sh
```

One-command real-data slices (download + convert + replay):

```bash
bash hardware_integration/xanadu/xandau_hardware_data.sh --install-deps

# QCA fig3b
bash hardware_integration/xanadu/xandau_hardware_data.sh \
  --dataset qca_fig3b \
  --max-shots 200000 \
  --install-deps
```

Full-data conversion (HPC recommended):

```bash
bash hardware_integration/xanadu/xandau_hardware_data.sh \
  --dataset aurora_full \
  --max-shots 0 \
  --progress-every 50000 \
  --install-deps
```

GKP full-data conversion:

```bash
bash hardware_integration/xanadu/xandau_hardware_data.sh \
  --dataset gkp_full \
  --max-shots 0 \
  --progress-every 50000 \
  --install-deps
```

By default, `gkp_full` uses compact count-table conversion (`metadata.repeat_count`)
to prevent multi-hundred-GB expanded NDJSON files. Set `LIDMAS_GKP_FULL_EXPAND=1`
only if you explicitly need one request row per shot.

Real Aurora decoder-demo batch:

```bash
python3 -m pip install numpy

python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format aurora_switch_dir \
  --stream \
  --input /path/to/decoder_demo/signal/batch_0 \
  --mapping hardware_integration/xanadu/xanadu_aurora_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_aurora.ndjson \
  --aurora-binarize \
  --max-shots 20000 \
  --progress-every 5000
```

Real QCA sample matrix:

```bash
python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping hardware_integration/xanadu/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --max-shots 50000 \
  --progress-every 10000
```

Chunk large QCA files by repeating conversion with shifted `--shot-start` and `--append-out`:

```bash
python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping hardware_integration/xanadu/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --shot-start 0 \
  --max-shots 200000

python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping hardware_integration/xanadu/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --append-out \
  --shot-start 200000 \
  --max-shots 200000
```

Count-compressed GKP outcomes:

```bash
python3 hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py \
  --source-format count_table_json \
  --input /path/to/gkp_outcome_counts.json \
  --mapping hardware_integration/xanadu/xanadu_gkp_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_gkp.ndjson
```

The mapping file controls how measured modes are converted to syndrome events.
See `hardware_integration/xanadu/xanadu_syndrome_mapping_example.json`.

Large-data controls:

- `--stream`: use memory-mapped loading where possible (notably `.npy`).
- `--shot-start`: skip the first `N` expanded shots.
- `--max-shots`: cap this run to `K` shots.
- `--append-out`: append to an existing NDJSON file.
- `--progress-every`: print progress every `M` written requests.

### Replay NDJSON through LiDMaS+ adapter

Use the C++ CLI replay mode to decode each NDJSON `DecodeRequest` line and write
NDJSON `DecodeResponse` lines:

```bash
./build/lidmas --decoder_io_replay \
  --decoder_io_in=examples/results/hardware_integration/decoder_requests.ndjson \
  --decoder_io_out=examples/results/hardware_integration/decoder_responses.ndjson \
  --decoder_io_config=schemas/surface_decoder_adapter_config.json \
  --decoder_io_continue_on_error
```

Use `--decoder_io_continue_on_error` to keep replaying when one line is malformed.

## C++ adapter API

Implement the `decoder_io::DecoderAdapter` interface:

```cpp
#include "decoder_io/DecoderAdapter.h"

class MyDecoder : public decoder_io::DecoderAdapter {
public:
    decoder_io::DecodeResponse decode(const decoder_io::DecodeRequest& request) override;
};
```

For surface-code streams, `decoder_io::SurfaceDecoderAdapter` provides a ready-made adapter that ingests
`SyndromeEvent`/`SyndromeDense` inputs and emits X/Z corrections separately.

You can load its configuration from JSON/YAML:

```cpp
#include "decoder_io/SurfaceDecoderAdapter.h"
#include "decoder_io/SurfaceDecoderConfigIO.h"

decoder_io::SurfaceDecoderAdapterConfig cfg;
std::string err;
if (!decoder_io::loadSurfaceDecoderAdapterConfig("decoder_config.json", &cfg, &err)) {
    throw std::runtime_error(err);
}
decoder_io::SurfaceDecoderAdapter adapter(cfg, registry);
```

Sample config: `schemas/surface_decoder_adapter_config.json`.

## Notes on syndrome types

Use `SyndromeType::X` or `SyndromeType::Z` for CSS/surface-code checks.
For codes with a single check type, use `Unknown`.
