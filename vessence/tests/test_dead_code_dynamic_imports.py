from agent_skills import dead_code_auditor
from agent_skills.dead_code_dynamic_imports import (
    dotted_dir_for_python_relpath,
    dynamic_import_prefixes_from_text,
    path_matches_dynamic_import_prefix,
)


def test_dead_code_auditor_uses_dynamic_import_helpers():
    assert dead_code_auditor._dynamic_import_prefixes_from_text is dynamic_import_prefixes_from_text
    assert dead_code_auditor._path_matches_dynamic_import_prefix is path_matches_dynamic_import_prefix


def test_dynamic_import_prefixes_from_text_matches_existing_import_patterns():
    text = """
    importlib.import_module(f"intent_classifier.v2.classes.{handler}")
    importlib.import_module("agent_skills.plugins." + name)
    __import__(f"context_builder.v1.parts.{part}")
    importlib.import_module(module_name)
    """

    assert dynamic_import_prefixes_from_text(text) == {
        "intent_classifier.v2.classes",
        "agent_skills.plugins",
        "context_builder.v1.parts",
    }


def test_dotted_dir_for_python_relpath_preserves_directory_level_matching():
    assert dotted_dir_for_python_relpath("intent_classifier/v2/classes/restart_server.py") == (
        "intent_classifier.v2.classes"
    )
    assert dotted_dir_for_python_relpath("agent_skills/example.py") == "agent_skills"


def test_path_matches_dynamic_import_prefix_checks_exact_and_nested_dirs():
    prefixes = {"intent_classifier.v2.classes", "agent_skills.plugins"}

    assert path_matches_dynamic_import_prefix("intent_classifier/v2/classes/restart_server.py", prefixes)
    assert path_matches_dynamic_import_prefix("intent_classifier/v2/classes/nested/tool.py", prefixes)
    assert path_matches_dynamic_import_prefix("agent_skills/plugins/example.py", prefixes)
    assert not path_matches_dynamic_import_prefix("agent_skills/standalone.py", prefixes)
