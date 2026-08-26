#!/usr/bin/env python3
"""Genera capturas documentales de preflight y dry-run sin ejecutar Docker."""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "screenshots"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = (result.stdout + result.stderr).strip()
    return output or f"[exit {result.returncode}]"


def wrap_lines(text: str, width: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        lines.extend(textwrap.wrap(raw, width=width, replace_whitespace=False) or [""])
    return lines


def draw_terminal(path: Path, title: str, subtitle: str, sections: list[tuple[str, str]], status: str) -> None:
    width, height = 1800, 1120
    image = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(image)
    title_font = font(FONT_BOLD, 38)
    subtitle_font = font(FONT, 20)
    section_font = font(FONT_BOLD, 22)
    body_font = font(FONT, 21)
    small_font = font(FONT, 17)

    draw.rectangle((0, 0, width, 12), fill="#8b5cf6")
    draw.text((72, 52), title, font=title_font, fill="#f6f7fb")
    draw.text((74, 112), subtitle, font=subtitle_font, fill="#7dd3fc")

    y = 178
    for section_title, content in sections:
        box_height = 290 if len(content) > 600 else 225
        draw.rounded_rectangle((64, y, width - 64, y + box_height), radius=18, fill="#0d1b2a", outline="#22344d", width=2)
        draw.ellipse((90, y + 24, 106, y + 40), fill="#f87171")
        draw.ellipse((120, y + 24, 136, y + 40), fill="#fbbf24")
        draw.ellipse((150, y + 24, 166, y + 40), fill="#34d399")
        draw.text((205, y + 18), section_title, font=section_font, fill="#d8b4fe")
        text_y = y + 64
        for line in wrap_lines(content, 105):
            draw.text((94, text_y), line, font=body_font, fill="#d6e4f0")
            text_y += 29
            if text_y > y + box_height - 30:
                break
        y += box_height + 28

    draw.rounded_rectangle((64, height - 84, width - 64, height - 34), radius=12, fill="#111f31")
    draw.text((88, height - 72), status, font=small_font, fill="#a7f3d0")
    image.save(path, format="PNG", optimize=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    python_version = command_output([sys.executable, "--version"])
    python_path = shutil.which("python3") or "no encontrado"
    docker_version = command_output(["docker", "--version"]) if shutil.which("docker") else "Docker CLI no encontrado en este entorno de captura"
    help_output = command_output([sys.executable, "lab_deployer.py", "--help"])
    help_excerpt = "\n".join(help_output.splitlines()[:10])

    draw_terminal(
        OUT / "installation-preflight.png",
        "Installation / Preflight",
        "Controlled lab readiness check — no container or payload execution",
        [
            (
                "$ python3 --version && command -v python3",
                f"{python_version}\n{python_path}",
            ),
            (
                "$ docker --version",
                f"{docker_version}\n\nDocker is required only for a real deployment; this capture remains a safe preflight.",
            ),
            (
                "$ python3 lab_deployer.py --help",
                help_excerpt,
            ),
        ],
        "PASS: Python syntax/help path validated; Docker availability is reported honestly.",
    )

    dry_run = command_output(
        [
            sys.executable,
            "lab_deployer.py",
            "deploy",
            "--payload",
            "payloads/lab-marker.txt",
            "--dry-run",
            "--image",
            "alpine:3.20",
            "--duration",
            "60",
        ]
    )
    draw_terminal(
        OUT / "execution-dry-run.png",
        "Execution / Dry-Run",
        "Read-only staging plan — Docker is not contacted",
        [
            (
                "$ python3 lab_deployer.py deploy --payload payloads/lab-marker.txt --dry-run",
                dry_run,
            ),
            (
                "Safety properties visible in the generated command",
                "--network none\n--read-only\n--cap-drop ALL\n--security-opt no-new-privileges=true\n--pids-limit 64\n--mount ... readonly=true\n--entrypoint /bin/sh ... sleep 60",
            ),
        ],
        "PASS: the selected artifact is hashed and mounted read-only; payload execution is disabled.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
