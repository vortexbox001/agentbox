#!/usr/bin/env bash
# pi harness entrypoint: register the LiteLLM proxy as a provider, then exec pi with the arguments
# the orchestrator built (same division of labour as the claude-code image).
set -euo pipefail
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
         "cost": {"input": 15, "output": 75, "cacheRead": 1.5, "cacheWrite": 18.75}}
      ]
    }
  }
}
JSON
exec pi "$@"
