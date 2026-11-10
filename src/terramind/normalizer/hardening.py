"""Project optional hardening facts, comparing before values only inside the client."""

import ipaddress
from typing import Any

from terramind.errors import InputError


def _marked(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_marked(item) for item in value.values())
    if isinstance(value, list):
        return any(_marked(item) for item in value)
    return value is True


def _at(value: Any, path: tuple[str | int, ...]) -> Any:
    for key in path:
        if value is True:
            return True
        if isinstance(key, str) and isinstance(value, dict):
            value = value.get(key)
        elif isinstance(key, int) and isinstance(value, list) and key < len(value):
            value = value[key]
        else:
            return None
    return value


def _value(change: dict[str, Any], phase: str, path: tuple[str | int, ...]) -> Any:
    if _marked(_at(change.get(f"{phase}_sensitive"), path)) or (
        phase == "after" and _marked(_at(change.get("after_unknown"), path))
    ):
        return None
    return _at(change.get(phase), path)


def _boolean(change: dict[str, Any], phase: str, path: tuple[str | int, ...]) -> bool | None:
    value = _value(change, phase, path)
    if value is not None and type(value) is not bool:
        raise InputError("Invalid hardening boolean")
    return value if isinstance(value, bool) else None


def _new(change: dict[str, Any], before: bool | None, after: bool | None) -> bool | None:
    if after is False:
        return False
    if after is None:
        return None
    if "create" in change["actions"]:
        return True
    return None if before is None else not before


def bucket_attributes(change: dict[str, Any]) -> dict[str, Any]:
    uniform = [
        _boolean(change, phase, ("uniform_bucket_level_access",)) for phase in ("before", "after")
    ]
    prevention = [
        _value(change, phase, ("public_access_prevention",)) for phase in ("before", "after")
    ]
    if any(value not in (None, "enforced", "inherited") for value in prevention):
        raise InputError("Invalid public access prevention setting")
    return {
        "public_access_prevention": prevention[1] or "unknown",
        "uniform_bucket_level_access": uniform[1],
        "newly_disabled_uniform_access": _new(
            change,
            None if uniform[0] is None else not uniform[0],
            None if uniform[1] is None else not uniform[1],
        ),
        "newly_inherited_prevention": _new(
            change,
            None if prevention[0] is None else prevention[0] == "inherited",
            None if prevention[1] is None else prevention[1] == "inherited",
        ),
    }


IP_PATH: tuple[str | int, ...] = ("settings", 0, "ip_configuration", 0)


def _world(change: dict[str, Any], phase: str) -> bool | None:
    networks = _value(change, phase, (*IP_PATH, "authorized_networks"))
    if networks is None:
        return None
    if not isinstance(networks, list) or len(networks) > 100:
        raise InputError("Invalid SQL authorized networks")
    world = False
    expiring_world = False
    for entry in networks:
        value = entry.get("value") if isinstance(entry, dict) else None
        if not isinstance(value, str) or len(value) > 128:
            raise InputError("Invalid SQL authorized network CIDR")
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise InputError("Invalid SQL authorized network CIDR") from None
        if network.version == 4 and network.prefixlen == 0:
            if entry.get("expiration_time"):
                expiring_world = True
            else:
                world = True
    return True if world else None if expiring_world else False


def _both(first: bool | None, second: bool | None) -> bool | None:
    if first is False or second is False:
        return False
    return True if first is True and second is True else None


def sql_attributes(change: dict[str, Any]) -> dict[str, Any]:
    ipv4 = [_boolean(change, phase, (*IP_PATH, "ipv4_enabled")) for phase in ("before", "after")]
    world = [_world(change, phase) for phase in ("before", "after")]
    modes = [_value(change, phase, (*IP_PATH, "ssl_mode")) for phase in ("before", "after")]
    if any(
        mode
        not in (
            None,
            "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
            "ENCRYPTED_ONLY",
            "TRUSTED_CLIENT_CERTIFICATE_REQUIRED",
        )
        for mode in modes
    ):
        raise InputError("Invalid SQL SSL mode")
    return {
        "ipv4_enabled": ipv4[1],
        "world_authorized_network": world[1],
        "newly_world_accessible": _new(change, _both(ipv4[0], world[0]), _both(ipv4[1], world[1])),
        "ssl_mode": modes[1] or "unknown",
        "newly_unencrypted": _new(
            change,
            None if modes[0] is None else modes[0] == "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
            None if modes[1] is None else modes[1] == "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
        ),
    }
