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
