"""Classroom Docker Compose policy.

Pure functions over an already-parsed Compose document (a dict). No file or
Docker I/O lives here, so the entire ruleset is unit-tested in CI without a host.

`validate_compose(doc, project_dir=...)` returns a list of human-readable
violation strings; an empty list means the Compose is allowed.
"""
from __future__ import annotations

import posixpath

MAX_SERVICES = 5
ALLOWED_HOST_IP = "127.0.0.1"

# Capabilities that would let a container escape or tamper with the host/kernel.
FORBIDDEN_CAPS = {
    "ALL", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_RAWIO", "SYS_BOOT",
    "SYS_TIME", "NET_ADMIN", "NET_RAW", "DAC_READ_SEARCH", "DAC_OVERRIDE",
    "MKNOD", "AUDIT_CONTROL", "SETFCAP",
}

# Host paths that must never be bind-mounted into a student container.
FORBIDDEN_SOURCES = (
    "/var/run/docker.sock", "/run/docker.sock",
    "/etc", "/root", "/boot", "/dev", "/proc", "/sys",
    "/var/lib/docker", "/srv/classroom",  # /srv/classroom handled specially below
)


def validate_compose(doc, *, project_dir="/srv/classroom/team", max_services=MAX_SERVICES):
    """Return a list of policy violations (empty = allowed)."""
    v: list[str] = []
    if not isinstance(doc, dict):
        return ["compose file is not a mapping"]

    if "version" in doc and str(doc["version"]).startswith("2"):
        # Compose v2 file format is fine, but we only note; not a violation.
        pass

    services = doc.get("services")
    if not isinstance(services, dict) or not services:
        return ["no services defined"]

    if len(services) > max_services:
        v.append(f"too many services: {len(services)} (max {max_services})")

    for name, svc in services.items():
        _check_service(name, svc or {}, project_dir, v)

    # Named volumes are rejected so all persistent data stays inside the team
    # directory (which is disk-quota'd). Students must bind-mount ./data instead.
    if doc.get("volumes"):
        vols = ", ".join(sorted(doc["volumes"].keys())) if isinstance(doc["volumes"], dict) else str(doc["volumes"])
        v.append(f"named volumes are not allowed ({vols}); bind-mount a path under your project dir instead")

    return v


def _check_service(name, svc, project_dir, v):
    where = f"service '{name}'"

    if not isinstance(svc, dict):
        v.append(f"{where}: not a mapping")
        return

    # --- Host namespace / privilege escapes --------------------------------
    if svc.get("privileged"):
        v.append(f"{where}: privileged is forbidden")
    for key in ("network_mode", "pid", "ipc"):
        val = svc.get(key)
        if isinstance(val, str) and (val == "host" or val.startswith("host")):
            v.append(f"{where}: {key}: {val} is forbidden")
    if svc.get("userns_mode") == "host":
        v.append(f"{where}: userns_mode: host is forbidden")

    for cap in _as_list(svc.get("cap_add")):
        if str(cap).upper().replace("CAP_", "") in FORBIDDEN_CAPS:
            v.append(f"{where}: cap_add {cap} is forbidden")

    # --- Image must be pinned ---------------------------------------------
    image = svc.get("image")
    if not image and "build" not in svc:
        v.append(f"{where}: no image and no build")
    if isinstance(image, str):
        tag = image.rsplit("@", 1)[0].rsplit(":", 1)
        if len(tag) == 1 or tag[-1] in ("latest", ""):
            v.append(f"{where}: image '{image}' must be pinned to an explicit tag (not latest)")

    # --- Resource limits, pids, logging, restart ---------------------------
    # Everything under deploy.resources.limits (cpus/memory/pids). Top-level
    # mem_limit/pids_limit conflict with the deploy block in Compose v2, so they
    # are rejected — the whole team is capped anyway by its cgroup slice.
    limits = (((svc.get("deploy") or {}).get("resources") or {}).get("limits")) or {}
    if "cpus" not in limits:
        v.append(f"{where}: missing CPU limit (deploy.resources.limits.cpus)")
    if "memory" not in limits:
        v.append(f"{where}: missing memory limit (deploy.resources.limits.memory)")
    if "pids" not in limits:
        v.append(f"{where}: missing pids limit (deploy.resources.limits.pids)")
    for legacy in ("pids_limit", "mem_limit"):
        if legacy in svc:
            v.append(f"{where}: use deploy.resources.limits, not top-level {legacy} (they conflict in Compose v2)")
    if "logging" not in svc:
        v.append(f"{where}: missing logging (log rotation required)")
    if "restart" not in svc and "restart_policy" not in (svc.get("deploy") or {}):
        v.append(f"{where}: missing restart policy")

    # --- Ports: only 127.0.0.1, never 0.0.0.0 ------------------------------
    for port in _as_list(svc.get("ports")):
        _check_port(where, port, v)

    # --- Volumes: no docker.sock, no host system paths, stay in project ----
    for vol in _as_list(svc.get("volumes")):
        _check_volume(where, vol, project_dir, v)


def _check_port(where, port, v):
    if isinstance(port, dict):
        host_ip = port.get("host_ip")
        published = port.get("published")
        if host_ip in (None, "", "0.0.0.0", "::"):
            v.append(f"{where}: port {published} must publish on {ALLOWED_HOST_IP} (got host_ip={host_ip!r})")
        elif host_ip != ALLOWED_HOST_IP:
            v.append(f"{where}: port {published} may only publish on {ALLOWED_HOST_IP} (got {host_ip})")
        return
    s = str(port)
    parts = s.split(":")
    # "80" or "8080:80" -> no host_ip -> binds 0.0.0.0 -> forbidden.
    if len(parts) < 3:
        v.append(f"{where}: port '{s}' must bind {ALLOWED_HOST_IP} explicitly (e.g. '127.0.0.1:8080:80')")
    else:
        host_ip = parts[0]
        if host_ip != ALLOWED_HOST_IP:
            v.append(f"{where}: port '{s}' may only bind {ALLOWED_HOST_IP} (got {host_ip})")


def _check_volume(where, vol, project_dir, v):
    if isinstance(vol, dict):
        if vol.get("type") == "bind":
            source = vol.get("source", "")
        elif vol.get("type") == "volume":
            v.append(f"{where}: named volume mounts are not allowed; bind-mount a path under your project dir")
            return
        else:
            source = vol.get("source", "")
    else:
        source = str(vol).split(":", 1)[0]

    if not source:
        return

    # Named volume (no path separator, not relative/absolute) -> rejected.
    if not source.startswith((".", "/", "~")):
        v.append(f"{where}: named volume '{source}' is not allowed; bind-mount a path under your project dir")
        return

    for bad in ("/var/run/docker.sock", "/run/docker.sock"):
        if source == bad or source.startswith(bad):
            v.append(f"{where}: mounting the Docker socket ({source}) is forbidden")
            return

    resolved = _resolve(source, project_dir)
    canon = posixpath.normpath(project_dir)
    if resolved != canon and not resolved.startswith(canon + "/"):
        v.append(f"{where}: bind mount '{source}' resolves outside the project dir ({resolved})")


def _resolve(source, project_dir):
    if source.startswith("~"):
        return posixpath.normpath("/nonexistent" + source[1:])  # ~ is never in project
    if source.startswith("/"):
        return posixpath.normpath(source)
    return posixpath.normpath(posixpath.join(project_dir, source))


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
