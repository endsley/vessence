"""self_improvement class — questions about Jane's nightly self-improve runs.

The nightly orchestrator writes vocal summaries to
$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl and a readable latest
report to $VESSENCE_HOME/configs/self_improvement_latest.md. When the
user asks what was fixed, improved, or audited, the Stage 2 handler
declines so Stage 3 (Opus) handles the response with the report path and
vocal summaries injected as context.
"""
