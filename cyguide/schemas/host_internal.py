"""Host-internal finding schemas (processes, files, packages)."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_host


class ProcessRunning(BaseFinding):
    """A running process on a host. Child of network.host. Produced by ps, netstat."""
    schema_type: str = "process.running"
    pik_fields: ClassVar[list[str]] = ["host_ip", "pid"]

    @classmethod
    def create(cls, host_ip: str, pid: int, name: str, **kwargs):
        normalized_ip = canonicalize_host(host_ip)
        return cls(
            pik={"host_ip": normalized_ip, "pid": pid},
            parent=Relation(target_type="network.host", target_pik={"ip": normalized_ip}, via="hosts_process"),
            data={"host_ip": normalized_ip, "pid": pid, "name": name, **kwargs}
        )

class FileSystemObject(BaseFinding):
    """A file or directory found on a host. Child of network.host. Produced by find, ls."""
    schema_type: str = "file.system_object"
    pik_fields: ClassVar[list[str]] = ["host_ip", "path"]

    @classmethod
    def create(cls, host_ip: str, path: str, **kwargs):
        normalized_ip = canonicalize_host(host_ip)
        return cls(
            pik={"host_ip": normalized_ip, "path": path},
            parent=Relation(target_type="network.host", target_pik={"ip": normalized_ip}, via="hosts_file"),
            data={"host_ip": normalized_ip, "path": path, **kwargs}
        )

class SoftwarePackage(BaseFinding):
    """An installed software package. Child of network.host. Produced by dpkg, rpm, brew."""
    schema_type: str = "software.package"
    pik_fields: ClassVar[list[str]] = ["host_ip", "package_name"]

    @classmethod
    def create(cls, host_ip: str, package_name: str, version: Optional[str] = None, **kwargs):
        normalized_ip = canonicalize_host(host_ip)
        return cls(
            pik={"host_ip": normalized_ip, "package_name": package_name},
            parent=Relation(target_type="network.host", target_pik={"ip": normalized_ip}, via="hosts_software"),
            data={"host_ip": normalized_ip, "package_name": package_name, "version": version, **kwargs}
        )
