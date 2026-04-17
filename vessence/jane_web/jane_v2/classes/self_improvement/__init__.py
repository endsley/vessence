"""self_improvement class — questions about Jane's nightly self-improve runs.

The nightly orchestrator writes vocal summaries to
$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl. When the user asks what
was fixed, improved, or audited, the Stage 2 handler declines so Stage 3
(Opus) handles the response with the vocal summaries injected as
context — the summaries are already TTS-friendly, so Opus can pick the
most relevant ones and read them conversationally without reciting code.
"""
