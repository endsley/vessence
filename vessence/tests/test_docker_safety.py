from agent_skills import safe_docker
from agent_skills.docker_safety import allowed_mount_bases, is_safe_mount


def test_safe_docker_uses_extracted_mount_safety_helpers() -> None:
    assert safe_docker._allowed_mount_bases is allowed_mount_bases
    assert safe_docker._is_safe_mount_path is is_safe_mount


def test_allowed_mount_bases_uses_real_paths_from_environment(tmp_path) -> None:
    code = tmp_path / "code"
    data = tmp_path / "data"
    vault = tmp_path / "vault"
    for path in (code, data, vault):
        path.mkdir()

    assert allowed_mount_bases({
        "VESSENCE_HOME": str(code),
        "VESSENCE_DATA_HOME": str(data),
        "VAULT_HOME": str(vault),
    }) == [str(code.resolve()), str(data.resolve()), str(vault.resolve())]


def test_is_safe_mount_accepts_allowed_base_or_child_and_rejects_prefix_sibling(tmp_path) -> None:
    base = tmp_path / "allowed"
    base.mkdir()
    child = base / "child"
    child.mkdir()
    sibling_prefix = tmp_path / "allowed_not_really"
    sibling_prefix.mkdir()

    bases = [str(base.resolve())]
    assert is_safe_mount(str(base), bases)
    assert is_safe_mount(str(child), bases)
    assert not is_safe_mount(str(sibling_prefix), bases)


def test_is_safe_mount_rejects_symlink_escape(tmp_path) -> None:
    base = tmp_path / "allowed"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    link = base / "escape"
    link.symlink_to(outside, target_is_directory=True)

    assert not is_safe_mount(str(link), [str(base.resolve())])
