DOCKER_LOG_SERVICES = {
    "backend": "equipment-agent-backend",
    "frontend": "equipment-agent-frontend",
    "postgres": "equipment-agent-postgres",
}


def get_container_logs(service: str, tail: int) -> str:
    try:
        import docker
    except ImportError as exc:
        raise RuntimeError("Docker SDK is not installed in the backend image.") from exc

    container_name = DOCKER_LOG_SERVICES[service]
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        raw_logs = container.logs(tail=tail, timestamps=True)
    except Exception as exc:
        raise RuntimeError(
            "Unable to read Docker logs. Ensure the backend container has access to the Docker socket."
        ) from exc

    return raw_logs.decode("utf-8", errors="replace")

