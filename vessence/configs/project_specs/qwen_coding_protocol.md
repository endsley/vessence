# Qwen Coding Protocol: High-Fidelity Autonomous Coding Pipeline

This document formalizes the multi-stage process for Qwen-led coding tasks, ensuring high-quality, verified, and contextually aware implementations.

## Management Layer: The Qwen Architect

The **Qwen Architect** (Master Agent) serves as the central orchestrator for the entire coding lifecycle. Its primary responsibilities include:
- **Task Decomposition:** Breaking down complex user requirements into modular sub-tasks.
- **Sub-Agent Coordination:** Dynamically spawning and managing specialized sub-agents for **Research**, **Implementation**, and **QA**.
- **State Management:** Maintaining a global 'Context Map' to ensure consistency across all pipeline stages.
- **Final Synthesis:** Integrating the outputs from specialized agents into a unified, production-ready solution.

## Pipeline Overview

### Stage 1: Spec Drafting (Requirement Synthesis)
- **Goal:** Transform ambiguous user requests into formal technical specifications.
- **Process:**
  - Analyze the initial prompt for core functional and non-functional requirements.
  - Identify potential edge cases and architectural constraints.
  - Produce a structured 'Implementation Plan' before any code is written.

### Stage 2: Best Practice Research (External Search)
- **Goal:** Incorporate current industry standards and library-specific patterns.
- **Process:**
  - Utilize search tools to identify the most efficient algorithms or libraries for the task.
  - Review documentation for any third-party APIs involved.
  - Ensure the proposed solution avoids known anti-patterns.

### Stage 3: Dependency Verification (Library Version & Syntax Refresh)
- **Goal:** Prevent version-mismatch errors and utilize modern syntax.
- **Process:**
  - Check `package.json`, `requirements.txt`, or equivalent for existing dependency versions.
  - Verify that the proposed code aligns with the installed versions.
  - Update internal 'knowledge' of specific library APIs via targeted documentation lookups if necessary.

### Stage 4: Contextual Harvesting (Local Type/Symbol Scout)
- **Goal:** Ensure seamless integration with the existing codebase.
- **Process:**
  - Use `grep_search` and `glob` to find related symbols, classes, and functions.
  - Extract type definitions and interface structures to maintain strict type safety.
  - Identify existing utility functions to avoid redundant implementations.

### Stage 5: Verified Implementation (Coding with Internal Linting)
- **Goal:** Produce clean, idiomatic, and error-free code.
- **Process:**
  - Implement the solution based on the synthesized spec and harvested context.
  - Apply project-specific styling and naming conventions.
  - Run available linters (e.g., `eslint`, `flake8`) and fix any reported issues immediately.

### Stage 6: Code Audit & Feedback (The Auditor)
- **Goal:** Identify logical flaws, security risks, and optimization opportunities.
- **Process:**
  - Command a separate 'Senior Code Auditor' persona to perform a deep dive into the implementation from Stage 5.
  - Generate a 'Feedback Report' detailing specific improvements.
  - The Architect must then decide if the code requires a refactoring pass based on this feedback before moving to QA.

### Stage 7: Autonomous Validation (Test Design, Execution, and Debugging)
- **Goal:** Confirm behavioral correctness and prevent regressions.
- **Process:**
  - Design a comprehensive test suite (unit and integration tests) covering the new logic.
  - Execute the tests and analyze failures.
  - Iteratively debug and refine the implementation until all tests pass and the spec is fully satisfied.

## Debugging & Observability Mandate

All generated code MUST prioritize transparency and maintainability through the following standards:
- **Python `logging` Module:** Use the standard `logging` module (or language-equivalent) for all execution tracking.
- **Ample Debug Information:** Logs must include entry/exit points for all major functions, internal state snapshots at critical decision points, and high-context error catching that includes local variable states.
- **Granular Log Levels:** Utilize `DEBUG` for verbose state information and `INFO` for high-level flow tracking, ensuring that production-level issues can be diagnosed without code changes.

