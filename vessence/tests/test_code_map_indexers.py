import ast
import textwrap

from agent_skills import generate_code_map
from agent_skills.code_map_indexers import (
    MAX_ENTRIES_PRIORITY,
    cap_entries,
    count_lines,
    index_file,
    index_html_file,
    index_kotlin_file,
    index_python_file,
    route_entry_from_decorator,
    should_skip,
)


def test_generate_code_map_reexports_indexers():
    assert generate_code_map.index_python_file is index_python_file
    assert generate_code_map._index_file is index_file
    assert generate_code_map._cap_entries is cap_entries


def test_index_python_file_extracts_routes_classes_functions_and_constants(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(textwrap.dedent("""\
        CONFIG_VALUE = 1

        @app.get("/health")
        def health():
            return "ok"

        async def worker():
            pass

        class Service:
            def run(self):
                pass
    """))

    entries = index_python_file(str(path))

    assert "  CONFIG_VALUE = ... → L1" in entries
    assert "  GET /health → L4" in entries
    assert any(entry.startswith("  worker() → L") for entry in entries)
    assert any(entry.startswith("  class Service → L") for entry in entries)
    assert any(entry.startswith("    run() → L") for entry in entries)
    assert count_lines(str(path)) == 12


def test_route_entry_from_decorator_extracts_supported_http_routes():
    tree = ast.parse('@app.patch("/items/{item_id}")\ndef update_item():\n    pass\n')
    func = tree.body[0]

    assert route_entry_from_decorator(func.decorator_list[0], func.lineno) == (
        "  PATCH /items/{item_id} → L2"
    )
    assert route_entry_from_decorator(ast.Name(id="other", ctx=ast.Load()), func.lineno) == ""


def test_index_html_file_extracts_methods_and_dedupes_events(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(textwrap.dedent("""\
        <script>
                async save() {
                  if (event.type === 'click') {}
                  if (event.type === 'click') {}
                }
        </script>
    """))

    entries = index_html_file(str(path))

    assert "  async save() → L2" in entries
    assert entries.count("  event.type === 'click' → L3") == 1


def test_index_kotlin_file_extracts_classes_composables_functions_and_constants(tmp_path):
    path = tmp_path / "Main.kt"
    path.write_text(textwrap.dedent("""\
        class MainActivity {
            companion object {
                const val REQUEST_CODE = 1
            }

            override fun onCreate() {}
        }

        @Composable
        fun Greeting() {}

        suspend fun loadData() {}
    """))

    entries = index_kotlin_file(str(path))

    assert "  class MainActivity → L1" in entries
    assert "    REQUEST_CODE → L3" in entries
    assert "    override onCreate() → L6" in entries
    assert "  @Composable Greeting() → L10" in entries
    assert "  suspend loadData() → L12" in entries


def test_index_file_dispatch_skip_rules_and_cap_entries(tmp_path):
    py_path = tmp_path / "sample.py"
    py_path.write_text("def one():\n    pass\n")

    assert index_file(str(py_path)) == ["  one() → L1-2"]
    assert should_skip("/repo/node_modules/pkg/file.py", "file.py")
    assert should_skip("/repo/pkg/__init__.py", "__init__.py")
    assert not should_skip("/repo/pkg/file.py", "file.py")

    entries = (
        [f"  class C{i} → L{i}" for i in range(5)]
        + [f"  GET /r{i} → L{i}" for i in range(5)]
        + [f"  fn{i}() → L{i}-{i}" for i in range(80)]
        + [f"  CONST_{i} = ... → L{i}" for i in range(5)]
    )

    capped = cap_entries(entries)

    assert len(capped) == MAX_ENTRIES_PRIORITY
    assert capped[:5] == [f"  class C{i} → L{i}" for i in range(5)]
    assert all("CONST_" not in entry for entry in capped)
