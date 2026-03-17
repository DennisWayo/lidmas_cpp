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

### Xanadu job conversion helper

Use the built-in converter example to transform Xanadu-style job outputs into
`DecodeRequest` NDJSON:

```bash
python3 examples/hardware_integration/convert_xanadu_job_to_decoder_io.py \
  --input /path/to/xanadu_job.json \
  --mapping /path/to/your_mapping.json \
  --out examples/results/hardware_integration/decoder_requests.ndjson
```

Quick demo:

```bash
bash examples/hardware_integration/run.sh
```

The mapping file controls how measured modes are converted to syndrome events.
See `examples/hardware_integration/xanadu_syndrome_mapping_example.json`.

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
