#!/usr/bin/env python3
"""
Despliegue seguro de artefactos en un laboratorio Docker.

Este complemento NO ejecuta el archivo seleccionado ni proporciona un canal de
entrega remota. Solo monta un artefacto como /lab/payload en un contenedor
controlado para inspección, validación de integridad y pruebas defensivas.

Uso autorizado: laboratorio local, CI aislado o ejercicio Purple Team con
alcance aprobado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


DEFAULT_IMAGE = "alpine:3.20"
DEFAULT_NETWORK = "none"
DEFAULT_MEMORY = "128m"
DEFAULT_CPUS = "0.50"
DEFAULT_PIDS_LIMIT = "64"
DEFAULT_DURATION = 900
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
LAB_LABEL = "msfvenom-payload-generator.lab=true"
CONTAINER_PREFIX = "msf-lab-"


class LabError(RuntimeError):
    """Error controlado del flujo de despliegue."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_name(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-.")
    if not candidate:
        raise LabError("El nombre del contenedor quedó vacío después del saneamiento.")
    if len(candidate) > 50:
        candidate = candidate[:50].rstrip("-.")
    return candidate


def resolve_payload(repo_root: Path, payload_root: str, requested: str, max_bytes: int) -> tuple[Path, Path]:
    allowed_root = (repo_root / payload_root).resolve()
    if not allowed_root.exists() or not allowed_root.is_dir():
        raise LabError(f"No existe el directorio de payloads permitido: {allowed_root}")

    raw_path = Path(requested).expanduser()
    unresolved = raw_path if raw_path.is_absolute() else (repo_root / raw_path)
    if unresolved.is_symlink():
        raise LabError("No se aceptan enlaces simbólicos como artefactos de laboratorio.")
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise LabError(
            f"La ruta debe permanecer dentro de {allowed_root}; se rechazó: {candidate}"
        ) from exc

    if not candidate.is_file():
        raise LabError(f"El artefacto no es un archivo regular: {candidate}")
    size = candidate.stat().st_size
    if size <= 0:
        raise LabError("El artefacto está vacío.")
    if size > max_bytes:
        raise LabError(f"El artefacto excede el máximo permitido de {max_bytes} bytes.")
    return candidate, allowed_root


def docker_binary() -> str:
    binary = shutil.which("docker")
    if not binary:
        raise LabError("No se encontró Docker en PATH. Instale Docker y vuelva a intentarlo.")
    return binary


def run_docker(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [docker_binary(), *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "sin salida").strip()
        raise LabError(f"Falló Docker ({result.returncode}): {detail}")
    return result


def validate_duration(value: str) -> int:
    try:
        duration = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("duration debe ser un entero") from exc
    if not 30 <= duration <= 86400:
        raise argparse.ArgumentTypeError("duration debe estar entre 30 y 86400 segundos")
    return duration


def validate_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("debe ser un entero positivo") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que cero")
    return parsed


def ensure_network_allowed(network: str, allow_network: bool) -> None:
    if network == DEFAULT_NETWORK:
        return
    if not allow_network:
        raise LabError(
            "La red está deshabilitada por defecto. Para usar una red Docker de laboratorio "
            "debe indicar --allow-network de forma explícita."
        )
    if network == "host" or network.startswith("container:"):
        raise LabError("No se permite --network host ni --network container:<id>.")


def image_available(image: str) -> bool:
    result = run_docker(["image", "inspect", image], check=False)
    return result.returncode == 0


def validate_image(image: str, pull: bool, dry_run: bool) -> None:
    if image.endswith(":latest") or image == "latest":
        raise LabError("No se permite la etiqueta mutable latest; use una versión concreta o un digest.")
    if dry_run:
        return
    if image_available(image):
        return
    if not pull:
        raise LabError(
            f"La imagen {image!r} no está disponible localmente. Use --pull solo cuando el origen "
            "de la imagen haya sido revisado y aprobado."
        )
    run_docker(["pull", image])


def build_run_command(
    *,
    image: str,
    name: str,
    payload: Path,
    network: str,
    memory: str,
    cpus: str,
    pids_limit: str,
    duration: int,
) -> list[str]:
    return [
        "run",
        "-d",
        "--name",
        name,
        "--label",
        LAB_LABEL,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev",
        "--tmpfs",
        "/run:rw,noexec,nosuid,nodev",
        "--pids-limit",
        pids_limit,
        "--cpus",
        cpus,
        "--memory",
        memory,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--network",
        network,
        "--mount",
        f"type=bind,src={payload},dst=/lab/payload,readonly=true",
        "--workdir",
        "/lab",
        "--user",
        "65532:65532",
        "--entrypoint",
        "/bin/sh",
        image,
        "-c",
        f"sleep {duration}",
    ]


def manifest_path(repo_root: Path, requested: str) -> Path:
    target = (repo_root / requested).resolve()
    allowed = (repo_root / "lab" / "manifests").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.relative_to(allowed)
    except ValueError as exc:
        raise LabError(f"El manifiesto debe almacenarse dentro de {allowed}") from exc
    return target


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def deploy(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parent
    payload, allowed_root = resolve_payload(repo_root, args.payload_root, args.payload, args.max_bytes)
    digest = sha256_file(payload)
    stem = safe_name(payload.stem)
    name = safe_name(args.name or f"{CONTAINER_PREFIX}{stem}-{digest[:10]}")
    ensure_network_allowed(args.network, args.allow_network)
    validate_image(args.image, args.pull, args.dry_run)

    command = build_run_command(
        image=args.image,
        name=name,
        payload=payload,
        network=args.network,
        memory=args.memory,
        cpus=args.cpus,
        pids_limit=str(args.pids_limit),
        duration=args.duration,
    )
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "mode": "non-executing-read-only-staging",
        "repository_root": str(repo_root),
        "payload_root": str(allowed_root),
        "payload": str(payload),
        "payload_size_bytes": payload.stat().st_size,
        "sha256": digest,
        "container_name": name,
        "image": args.image,
        "network": args.network,
        "limits": {
            "memory": args.memory,
            "cpus": args.cpus,
            "pids_limit": args.pids_limit,
        },
        "mount": {"source": str(payload), "destination": "/lab/payload", "read_only": True},
        "command": ["sleep", args.duration],
        "payload_execution_requested": False,
        "status": "dry-run" if args.dry_run else "planned",
    }
    manifest_file = manifest_path(repo_root, args.manifest)
    write_manifest(manifest_file, manifest)

    print("[lab] Despliegue controlado de artefacto")
    print(f"[lab] Artefacto : {payload}")
    print(f"[lab] SHA-256   : {digest}")
    print(f"[lab] Contenedor: {name}")
    print(f"[lab] Imagen    : {args.image}")
    print(f"[lab] Red       : {args.network}")
    print("[lab] Ejecución : DESHABILITADA; solo montaje read-only")
    print(f"[lab] Manifiesto: {manifest_file}")
    print("[lab] Comando Docker:")
    print("  " + " ".join(command))

    if args.dry_run:
        print("[lab] Dry-run completado; no se contactó con Docker.")
        return 0

    existing = run_docker(["container", "inspect", name], check=False)
    if existing.returncode == 0:
        raise LabError(f"Ya existe un contenedor con el nombre {name!r}; use --name distinto.")

    container_id = run_docker(command).stdout.strip()
    manifest["status"] = "running"
    manifest["container_id"] = container_id
    write_manifest(manifest_file, manifest)
    print(f"[lab] Contenedor iniciado: {container_id[:12]}")
    print(f"[lab] Detener : python3 lab_deployer.py stop --name {name}")
    print(f"[lab] Eliminar: python3 lab_deployer.py stop --name {name} --remove")
    return 0


def stop(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    run_docker(["container", "stop", "--time", "10", name])
    if args.remove:
        run_docker(["container", "rm", name])
    print(f"[lab] Contenedor detenido: {name}")
    if args.remove:
        print(f"[lab] Contenedor eliminado: {name}")
    return 0


def inspect_container(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    result = run_docker(["container", "inspect", name])
    print(result.stdout, end="")
    return 0


def list_containers(_: argparse.Namespace) -> int:
    result = run_docker(
        [
            "ps",
            "-a",
            "--filter",
            f"label={LAB_LABEL}",
            "--format",
            "table {{.Names}}\\t{{.Status}}\\t{{.Image}}\\t{{.Networks}}",
        ]
    )
    print(result.stdout, end="")
    return 0


def cleanup(args: argparse.Namespace) -> int:
    if not args.confirm:
        raise LabError("cleanup requiere --confirm para detener y eliminar contenedores del laboratorio.")
    result = run_docker(
        ["ps", "-aq", "--filter", f"label={LAB_LABEL}"],
        check=True,
    )
    ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not ids:
        print("[lab] No hay contenedores del laboratorio para limpiar.")
        return 0
    run_docker(["rm", "-f", *ids])
    print(f"[lab] Contenedores eliminados: {len(ids)}")
    return 0


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", help="muestra el plan y no ejecuta Docker")

    root = argparse.ArgumentParser(
        description="Despliegue no ejecutable de artefactos en un laboratorio Docker aislado."
    )
    sub = root.add_subparsers(dest="command", required=True)

    deploy_parser = sub.add_parser("deploy", parents=[common], help="monta un artefacto en un contenedor aislado")
    deploy_parser.add_argument("--payload", required=True, help="ruta relativa al archivo dentro de payloads/")
    deploy_parser.add_argument("--payload-root", default="payloads", help="directorio permitido; por defecto payloads")
    deploy_parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"imagen local; por defecto {DEFAULT_IMAGE}")
    deploy_parser.add_argument("--pull", action="store_true", help="permite descargar la imagen si no existe localmente")
    deploy_parser.add_argument("--name", help="nombre explícito del contenedor")
    deploy_parser.add_argument("--network", default=DEFAULT_NETWORK, help="none por defecto; red Docker de laboratorio opcional")
    deploy_parser.add_argument("--allow-network", action="store_true", help="confirma conscientemente una red distinta de none")
    deploy_parser.add_argument("--memory", default=DEFAULT_MEMORY, help=f"límite de memoria; por defecto {DEFAULT_MEMORY}")
    deploy_parser.add_argument("--cpus", default=DEFAULT_CPUS, help=f"límite de CPU; por defecto {DEFAULT_CPUS}")
    deploy_parser.add_argument("--pids-limit", type=validate_positive_int, default=int(DEFAULT_PIDS_LIMIT), help="límite de procesos")
    deploy_parser.add_argument("--duration", type=validate_duration, default=DEFAULT_DURATION, help="duración del contenedor en segundos")
    deploy_parser.add_argument("--max-bytes", type=validate_positive_int, default=DEFAULT_MAX_BYTES, help="tamaño máximo del archivo")
    deploy_parser.add_argument("--manifest", default="lab/manifests/last-deploy.json", help="ruta del manifiesto dentro de lab/manifests/")
    deploy_parser.set_defaults(func=deploy)

    stop_parser = sub.add_parser("stop", help="detiene un contenedor del laboratorio")
    stop_parser.add_argument("--name", required=True)
    stop_parser.add_argument("--remove", action="store_true", help="elimina el contenedor después de detenerlo")
    stop_parser.set_defaults(func=stop)

    inspect_parser = sub.add_parser("inspect", help="muestra la inspección Docker de un contenedor")
    inspect_parser.add_argument("--name", required=True)
    inspect_parser.set_defaults(func=inspect_container)

    list_parser = sub.add_parser("list", help="lista contenedores creados por este complemento")
    list_parser.set_defaults(func=list_containers)

    cleanup_parser = sub.add_parser("cleanup", help="detiene y elimina todos los contenedores etiquetados del laboratorio")
    cleanup_parser.add_argument("--confirm", action="store_true", help="confirma la operación destructiva")
    cleanup_parser.set_defaults(func=cleanup)

    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.func(args))
    except LabError as exc:
        print(f"[lab][ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n[lab] Interrumpido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
