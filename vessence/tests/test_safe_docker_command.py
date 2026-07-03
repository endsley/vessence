from agent_skills import safe_docker
from agent_skills.safe_docker_command import docker_run_command, safe_container_name


def test_safe_docker_uses_extracted_command_helpers():
    assert safe_docker._safe_container_name is safe_container_name
    assert safe_docker._docker_run_command is docker_run_command


def test_safe_container_name_uses_first_eight_uuid_chars():
    assert safe_container_name("abcdef123456") == "safe_abcdef12"


def test_docker_run_command_preserves_option_order_without_gpu():
    assert docker_run_command(
        container_name="safe_abc",
        image="image:latest",
        args=["cmd", "arg"],
        volumes={"/host": "/container"},
        env={"A": "1", "B": "2"},
        memory="2g",
        cpus=1,
    ) == [
        "docker",
        "run",
        "--rm",
        "--name",
        "safe_abc",
        "--memory=2g",
        "--cpus=1",
        "-e",
        "A=1",
        "-e",
        "B=2",
        "-v",
        "/host:/container",
        "image:latest",
        "cmd",
        "arg",
    ]


def test_docker_run_command_includes_gpu_flag_when_enabled():
    assert docker_run_command(
        container_name="safe_abc",
        image="image",
        gpu_enabled=True,
    ) == [
        "docker",
        "run",
        "--rm",
        "--name",
        "safe_abc",
        "--memory=4g",
        "--cpus=2",
        "--gpus",
        "all",
        "image",
    ]
