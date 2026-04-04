# Qwen Sub-Agent Interface Specification

This document defines the formal 'API' for communication between the Master Architect and the specialized sub-agents. All exchanges must adhere to these schemas to ensure project state integrity and successful execution.

## The Context Package (Project State)

The 'Context Package' is the source of truth passed between stages. It is a structured JSON or Markdown document stored in `configs/project_specs/current_task_state.md`.

**Core State Fields:**
- `task_id`: Unique identifier for the current request.
- `specification_path`: Path to the Stage 1 Markdown spec.
- `research_report`: Findings from the Research Sub-Agent.
- `context_map`: Symbols, types, and file paths found by the Context Scout.
- `implementation_log`: Path to implemented files and verbose logs.
- `test_results`: Reports from the QA Engineer.
- `status`: [PENDING | RESEARCHING | SCOUTING | IMPLEMENTING | VALIDATING | COMPLETE | FAILED].

---

## 1. Research Sub-Agent (Stage 2)

**Persona:** Technical Librarian / Lead Researcher.
**Objective:** Identify best practices, library versions, and architectural patterns.

### Input Schema:
- `objective`: High-level goal from the Specification.
- `constraints`: Specific library or version requirements (if any).
- `workspace_tech_stack`: Existing languages and frameworks detected.

### Output Schema:
- `recommended_libraries`: List of libraries with specific versions and rationale.
- `best_practices`: Coding standards and patterns applicable to this task.
- `dependency_deltas`: New packages that must be installed.
- `risk_assessment`: Potential conflicts or performance bottlenecks.

---

## 2. Context Scout (Stage 3 & 4)

**Persona:** Codebase Explorer / Systems Analyst.
**Objective:** Map local types, symbols, and environment readiness.

### Input Schema:
- `target_directories`: Areas of the codebase relevant to the task.
- `symbol_query`: Specific types, classes, or functions to locate.
- `environment_check`: List of required paths, environment variables, or permissions.

### Output Schema:
- `symbol_registry`: Map of `{symbol_name: file_path}` and associated type definitions.
- `utility_discovery`: Existing helper functions that should be reused.
- `environment_status`: [READY | BLOCKED (with reason)].
- `path_mapping`: Verified absolute paths for all target operations.

---

## 3. Implementer (Stage 5)

**Persona:** Senior Software Engineer.
**Objective:** Produce clean, idiomatic code with high observability.

### Input Schema:
- `specification`: The Stage 1 Markdown spec.
- `research_context`: The Research Sub-Agent's report.
- `context_map`: The Context Scout's findings.
- `coding_standards`: Project-specific style guides.

### Output Schema:
- `implemented_files`: List of new/modified file paths.
- `implementation_notes`: Decisions made during coding.
- `verbose_logs`: Path to execution logs or `stdout` captures.
- `diff_summary`: High-level summary of changes.

---

## 4. QA Engineer (Stage 6)

**Persona:** SDET / Quality Assurance Specialist.
**Objective:** Verify correctness through automated testing and debug analysis.

### Input Schema:
- `implemented_code`: Access to the files produced by the Implementer.
- `test_requirements`: Edge cases and functional requirements from the Spec.
- `logs`: Implementation-phase logs for debug analysis.

### Output Schema:
- `test_suite_path`: Path to the generated test scripts.
- `execution_results`: [PASS | FAIL] per test case.
- `debug_report`: Deep-dive analysis of any failures, including log correlation.
- `validation_verdict`: Final recommendation for Stage 6 completion.
