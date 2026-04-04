#!/usr/bin/env python3
import sys
import os
import json
import logging
import requests
import ollama
import importlib.util
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
from jane.config import CONFIGS_DIR, LOGS_DIR, VESSENCE_HOME

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'qwen_orchestrator.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("QwenOrchestrator")

class QwenOrchestrator:
    def __init__(self):
        self.model = LOCAL_LLM_MODEL
        self.state_file = os.path.join(CONFIGS_DIR, 'project_specs', 'current_task_state.json')
        self.persona_path = os.path.join(CONFIGS_DIR, 'prompts', 'qwen_architect_master.txt')
        self.protocol_path = os.path.join(CONFIGS_DIR, 'project_specs', 'qwen_coding_protocol.md')
        self.auditor_persona = (
            "You are a Senior Code Auditor. Your goal is to critically review code for logical flaws, "
            "security vulnerabilities, and performance bottlenecks. Provide specific, actionable feedback."
        )
        
        try:
            with open(self.persona_path, 'r') as f:
                self.master_persona = f.read()
        except FileNotFoundError:
            logger.warning(f"Persona file not found at {self.persona_path}. Using default persona.")
            self.master_persona = "You are a senior software architect. Provide expert technical guidance."

    def check_hardware_lock(self):
        """Verify Ollama is reachable."""
        try:
            requests.get("http://localhost:11434/api/tags", timeout=2)
            return True
        except Exception:
            logger.critical("OFFLINE: Local Ollama service unreachable. Aborting to protect Gemini quota.")
            return False

    def query_qwen(self, prompt, system_override=None):
        """Core local LLM call."""
        if not self.check_hardware_lock():
            sys.exit(1)
        
        system_instr = system_override or self.master_persona
        
        logger.info("--- STARTING LOCAL QWEN CALL (OLLAMA) ---")
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instr},
                    {"role": "user", "content": prompt}
                ]
            )
            logger.info("--- LOCAL QWEN RESPONSE RECEIVED ---")
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            return None

    def update_state(self, stage, status, details=None):
        state = {"stage": stage, "status": status, "details": details}
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"State Updated: Stage {stage} -> {status}")

    def stage_1_spec(self, user_request):
        self.update_state(1, "running")
        prompt = f"STAGE 1: SPEC DRAFTING. Task: {user_request}. Output a formal Markdown spec."
        result = self.query_qwen(prompt)
        if result:
            spec_path = os.path.join(CONFIGS_DIR, 'project_specs', 'active_spec.md')
            with open(spec_path, 'w') as f:
                f.write(result)
            self.update_state(1, "completed", f"Spec saved to {spec_path}")
        return result

    def stage_2_research(self, topic):
        self.update_state(2, "running")
        prompt = f"STAGE 2: BEST PRACTICE RESEARCH. Topic: {topic}. Identify libraries and patterns."
        result = self.query_qwen(prompt)
        self.update_state(2, "completed")
        return result

    def stage_3_dependency(self):
        self.update_state(3, "running")
        requirements_file = os.path.join(VESSENCE_HOME, 'requirements.txt')
        if not os.path.exists(requirements_file):
            logger.error(f"Requirements file not found: {requirements_file}")
            self.update_state(3, "failed", "requirements.txt not found")
            return None
        
        status_report = {}
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.split('#')[0].strip()
                    if not line:
                        continue
                    
                    package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0].strip()
                    search_name = package_name.replace('-', '_')
                    spec = importlib.util.find_spec(search_name)
                    if not spec:
                        spec = importlib.util.find_spec(package_name)
                    
                    status_report[package_name] = "INSTALLED" if spec else "MISSING"
                    logger.info(f"Dependency {package_name}: {status_report[package_name]}")
        except Exception as e:
            logger.error(f"Error reading requirements.txt: {e}")
            self.update_state(3, "failed", str(e))
            return None
            
        self.update_state(3, "completed", json.dumps(status_report))
        return status_report

    def stage_4_harvest(self):
        self.update_state(4, "running")
        search_dir = os.path.join(VESSENCE_HOME, 'agent_skills') + '/'
        patterns = ["class ", "def ", "logging.", "try:"]
        harvested_context = ""
        
        for pattern in patterns:
            try:
                cmd = ["grep", "-r", "-n", "--include=*.py", pattern, search_dir]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.stdout:
                    lines = result.stdout.splitlines()[:5]
                    harvested_context += f"--- Matches for '{pattern}' ---\n"
                    harvested_context += "\n".join(lines) + "\n\n"
            except Exception as e:
                logger.error(f"Harvesting failed for pattern '{pattern}': {e}")
                
        if not harvested_context:
            harvested_context = "No idiomatic context harvested."
            
        logger.info("Context harvesting complete.")
        self.update_state(4, "completed", "Harvested idiomatic snippets.")
        return harvested_context

    def stage_5_implement(self, spec_content):
        self.update_state(5, "running")
        prompt = f"STAGE 5: IMPLEMENTATION. Using this spec:\n{spec_content}\nWrite the final Python code."
        result = self.query_qwen(prompt)
        self.update_state(5, "completed")
        return result

    def stage_6_audit(self, code):
        self.update_state(6, "running")
        prompt = f"STAGE 6: AUDIT & FEEDBACK. Critically review this code and provide feedback:\n{code}"
        result = self.query_qwen(prompt, system_override=self.auditor_persona)
        self.update_state(6, "completed", "Audit report generated.")
        return result

    def stage_7_validate(self, code):
        self.update_state(7, "running")
        prompt = f"STAGE 7: VALIDATION. Write a pytest suite for this code:\n{code}"
        result = self.query_qwen(prompt)
        self.update_state(7, "completed")
        return result

if __name__ == "__main__":
    # Initialize the orchestrator
    orchestrator = QwenOrchestrator()

    # Verify Ollama hardware lock before starting
    if not orchestrator.check_hardware_lock():
        sys.exit(1)

    # Get task description from command line arguments
    if len(sys.argv) < 2:
        print("Usage: python3 qwen_orchestrator.py <task_description>")
        logger.error("No task description provided.")
        sys.exit(1)
    
    task = " ".join(sys.argv[1:])
    logger.info(f"--- INITIALIZING MASTER ARCHITECT PROTOCOL (7-STAGE) ---")
    logger.info(f"Task: {task}")

    # Stage 1: Specification
    logger.info("Executing Stage 1: Specification (Spec Definition)")
    spec = orchestrator.stage_1_spec(task)
    if not spec:
        logger.error("Stage 1 failed: Specification could not be drafted.")
        sys.exit(1)

    # Stage 2: Research
    logger.info("Executing Stage 2: Research (Best Practices & Stack)")
    research = orchestrator.stage_2_research(task)
    if not research:
        logger.error("Stage 2 failed: Research could not be completed.")
        sys.exit(1)

    # Stage 3: Dependency Check
    logger.info("Executing Stage 3: Dependency Check (Context Scouting)")
    deps = orchestrator.stage_3_dependency()
    if not deps:
        logger.error("Stage 3 failed: Dependency check could not be completed.")
        sys.exit(1)

    # Stage 4: Context Harvest
    logger.info("Executing Stage 4: Context Harvest (Idiomatic Integration)")
    harvest = orchestrator.stage_4_harvest()
    if not harvest:
        logger.error("Stage 4 failed: Context harvesting could not be completed.")
        sys.exit(1)

    # Stage 5: Implementation
    logger.info("Executing Stage 5: Implementation (Build & Log)")
    code = orchestrator.stage_5_implement(spec)
    if not code:
        logger.error("Stage 5 failed: Code could not be implemented.")
        sys.exit(1)

    # Stage 6: Audit
    logger.info("Executing Stage 6: Audit (QA & Validation)")
    audit_feedback = orchestrator.stage_6_audit(code)
    if not audit_feedback:
        logger.error("Stage 6 failed: Code audit could not be completed.")
        sys.exit(1)

    # Stage 7: Validation
    logger.info("Executing Stage 7: Validation (Write Test Suite)")
    validate_results = orchestrator.stage_7_validate(code)
    if not validate_results:
        logger.error("Stage 7 failed: Validation suite could not be written.")
        sys.exit(1)

    # Final Execution Summary
    logger.info("--- 7-STAGE PIPELINE COMPLETED SUCCESSFULLY ---")
    logger.info("Results Summary:")
    logger.info("  [1] Specification:   [DONE]")
    logger.info("  [2] Research:        [DONE]")
    logger.info("  [3] Dependency:      [DONE]")
    logger.info("  [4] Harvest:         [DONE]")
    logger.info("  [5] Implementation:  [DONE]")
    logger.info("  [6] Audit:           [DONE]")
    logger.info("  [7] Validation:      [DONE]")
    print("\n--- MASTER ARCHITECT PROTOCOL COMPLETE ---")
    print("\n--- STAGE 5: IMPLEMENTATION CODE ---")
    print(code)
    print("\n--- STAGE 6: AUDIT FEEDBACK ---")
    print(audit_feedback)
    print("\n--- STAGE 7: VALIDATION SUITE ---")
    print(validate_results)
