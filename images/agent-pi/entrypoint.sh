#!/usr/bin/env bash
# pi harness entrypoint: register the LiteLLM proxy as a provider, then exec pi with the arguments
# the orchestrator built (same division of labour as the claude-code image).
set -euo pipefail
# costs are USD per 1M tokens: Anthropic list prices; Moonshot from platform.kimi.ai/docs/pricing
mkdir -p "$HOME/.pi/agent"
cat > "$HOME/.pi/agent/models.json" <<JSON
{
  "providers": {
    "litellm": {
      "baseUrl": "${LITELLM_URL:-http://litellm:4000/v1}",
      "api": "openai-completions",
      "apiKey": "${LITELLM_MASTER_KEY:?LITELLM_MASTER_KEY required}",
      "models": [
        {"id": "cheap", "name": "cheap (LiteLLM alias)", "reasoning": true, "input": ["text"],
         "contextWindow": 200000, "maxTokens": 8192,
         "cost": {"input": 1, "output": 5, "cacheRead": 0.1, "cacheWrite": 1.25}},
        {"id": "smart", "name": "smart (LiteLLM alias)", "reasoning": true, "input": ["text"],
         "contextWindow": 200000, "maxTokens": 16384,
         "cost": {"input": 3, "output": 15, "cacheRead": 0.3, "cacheWrite": 3.75}},
        {"id": "opus", "name": "opus (LiteLLM alias)", "reasoning": true, "input": ["text"],
         "contextWindow": 200000, "maxTokens": 32000,
         "cost": {"input": 15, "output": 75, "cacheRead": 1.5, "cacheWrite": 18.75}},
        {"id": "kimi", "name": "kimi (LiteLLM alias: kimi-k2.7-code)", "reasoning": true, "input": ["text"],
         "contextWindow": 262144, "maxTokens": 32000,
         "cost": {"input": 0.95, "output": 4, "cacheRead": 0.19, "cacheWrite": 0.95}},
        {"id": "kimi-k3", "name": "kimi-k3 (LiteLLM alias)", "reasoning": true, "input": ["text"],
         "contextWindow": 1048576, "maxTokens": 32000,
         "cost": {"input": 3, "output": 15, "cacheRead": 0.3, "cacheWrite": 3}}
      ]
    }
  }
}
JSON
# Accept `--thinking max`, which pi itself rejects, so the YAML `effort` key means the same thing on
# every harness: the model's highest level. Kimi's native default *is* max, so drop the flag there;
# for everything else substitute pi's ceiling, xhigh.
args=(); model=""; prev=""
for a in "$@"; do
  [ "$prev" = "--model" ] && model=$a
  prev=$a
done
skip=0
for a in "$@"; do
  if [ $skip -eq 1 ]; then skip=0; continue; fi
  if [ "$a" = "--thinking" ]; then
    # peek at the level that follows
    lvl=""; found=0
    for b in "$@"; do
      if [ $found -eq 1 ]; then lvl=$b; break; fi
      [ "$b" = "--thinking" ] && found=1
    done
    if [ "$lvl" = "max" ]; then
      skip=1
      case "$model" in
        litellm/kimi*) ;;                       # native default is max: pass nothing
        *) args+=(--thinking xhigh) ;;
      esac
      continue
    fi
  fi
  args+=("$a")
done
exec pi "${args[@]}"
