# Hardware Integration

LiDMaS+ supports three data ingestion modes for hardware integration:

1. gRPC streaming (recommended)
2. File batch (NDJSON)
3. In-process C++ adapter API

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
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format xanadu_job_json \
  --input /path/to/xanadu_job.json \
  --mapping /path/to/your_mapping.json \
  --out examples/results/hardware_integration/decoder_requests.ndjson
```

Quick demo:

```bash
bash examples/hardware_integration/run.sh
```

Aurora / QCA / GKP fixture demos:

```bash
bash examples/hardware_integration/run_public_datasets.sh
```

Real Aurora decoder-demo batch:

```bash
python3 -m pip install numpy

python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format aurora_switch_dir \
  --stream \
  --input /path/to/decoder_demo/signal/batch_0 \
  --mapping examples/hardware_integration/xanadu_aurora_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_aurora.ndjson \
  --aurora-binarize \
  --max-shots 20000 \
  --progress-every 5000
```

Real QCA sample matrix:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --max-shots 50000 \
  --progress-every 10000
```

Chunk large QCA files by repeating conversion with shifted `--shot-start` and `--append-out`:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --shot-start 0 \
  --max-shots 200000

python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format shot_matrix \
  --stream \
  --input /path/to/fig3a/samples.npy \
  --mapping examples/hardware_integration/xanadu_qca_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_qca.ndjson \
  --append-out \
  --shot-start 200000 \
  --max-shots 200000
```

Count-compressed GKP outcomes:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --source-format count_table_json \
  --input /path/to/gkp_outcome_counts.json \
  --mapping examples/hardware_integration/xanadu_gkp_mapping_example.json \
  --out examples/results/hardware_integration/decoder_requests_gkp.ndjson
```

The mapping file controls how measured modes are converted to syndrome events.
See `examples/hardware_integration/xanadu_syndrome_mapping_example.json`.

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
