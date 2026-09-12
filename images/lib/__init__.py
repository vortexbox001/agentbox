"""Shared, image-side library copied into every harness image.

Currently holds ``agent_report`` — the common run-report shape and its Dagster
Pipes emit path — so every harness (api, claude-code, codex, pi) reports itself
in one identical structure (spec 007 / Constitution IV).
"""
