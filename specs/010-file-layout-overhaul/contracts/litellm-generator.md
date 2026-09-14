# Contract: LiteLLM Generator (`litellm/generate.py`)

## §1 Invocation

```
python3 litellm/generate.py                  # merge → write config/litellm.rendered.yaml
```

Runs **on demand** (CLI, above) and **at stack start** (compose init step / entrypoint that
runs before the LiteLLM container loads its config) — FR-016.

Inputs:
- Template: `litellm/config.template.yaml` (product; alias tiers `cheap`, `smart`, `opus`,
  `kimi`, `kimi-k3`).
- Overlay: `$AGENTBOX_CONFIG/litellm.overlay.yaml` (instance; providers, `api_key` env-var
  names, `api_base`, alias→model bindings, pricing).
- Environment: the process env (for the missing-key check only — values are never written).

Output: `$AGENTBOX_CONFIG/litellm.rendered.yaml` — the sole file the LiteLLM container mounts and
loads (FR-014).

## §2 Merge semantics

- Deep-merge overlay over template: the overlay supplies each tier's concrete
  `model`/`api_base`/`api_key`/pricing and MAY add providers; the template supplies the tier
  names features depend on. Overlay values win on conflict.
- `api_key` fields stay as `os.environ/<NAME>` references in the rendered file — **never**
  expanded to a value (Constitution III).

## §3 Behavioural requirements

- **R-LL-1 (US6-1)**: given the template + an overlay naming providers/bindings, the rendered
  config binds the product's alias tiers to the instance's providers.
- **R-LL-2 (FR-017, US6-2, SC-008)**: for every `api_key: os.environ/<NAME>` the merged config
  references, `<NAME>` must be present in the environment. If any is missing, the generator
  **exits non-zero naming the missing key(s)** and does **not** write a rendered config (so there
  is no config whose only failure is at first request).
- **R-LL-3 (FR-014)**: the rendered file is written under the config root and is the path the
  compose LiteLLM service mounts; the product template is never mounted directly.
- **R-LL-4**: the rendered file is gitignored within the config repo (documented in
  `.gitignore` guidance for the config tree).

## §4 Tests

- Unit: template + overlay fixtures → assert rendered `model_list` binds each tier to the
  overlay's provider/model and preserves `os.environ/` refs (R-LL-1, R-LL-2 negative-of).
- Unit: overlay references `MISSING_KEY` absent from env → assert non-zero exit, the name
  `MISSING_KEY` in the message, and **no** output file written (R-LL-2).
- Unit: `api_key` value never appears expanded in the rendered output (Constitution III).
