#!/usr/bin/env python3
"""Servidor local para editar config.json desde el navegador (make config-ui)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
HTML_PATH = ROOT / "config-editor.html"
OUT_GEMINI = ROOT / "out" / "answers_gemini.json"
OUT_RETAKE = ROOT / "out" / "answers_retake.json"
DEFAULT_PORT = 8765
RUN_TIMEOUT = 600

DEFAULT_CONFIG: dict[str, Any] = {
    "base_url": "https://campusvirtual.colombia.unir.net",
    "attempt": 0,
    "cmid": 0,
    "cookie": "",
    "answers": {},
    "finish_attempt": True,
    "finalize_after_summary": True,
    "confirm_submit": True,
}

EDITABLE_KEYS = (
    "base_url",
    "attempt",
    "cmid",
    "cookie",
    "answers",
    "finish_attempt",
    "finalize_after_summary",
    "confirm_submit",
)

ALLOWED_ACTIONS = frozenset({"gemini", "submit", "dry-run"})


def load_config_file() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        return dict(DEFAULT_CONFIG)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config.json debe ser un objeto JSON.")
    return data


def merge_for_save(existing: dict[str, Any], submitted: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in EDITABLE_KEYS:
        if key in submitted:
            merged[key] = submitted[key]
    for key, value in existing.items():
        if key.startswith("_") and key not in merged:
            merged[key] = value
    if "gemini" in existing and "gemini" not in submitted:
        merged["gemini"] = existing["gemini"]
    if "next_finish" in existing and "next_finish" not in submitted:
        merged["next_finish"] = existing["next_finish"]
    return merged


def write_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_answers_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path.relative_to(ROOT)}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("El archivo de respuestas debe ser un objeto JSON.")
    return data


def docker_run_cmd(*args: str) -> list[str]:
    return ["docker", "compose", "run", "--rm", "-T", "moodle-quiz", *args]


def build_action_cmd(action: str, model: str | None = None) -> list[str]:
    if action == "gemini":
        cmd = docker_run_cmd(
            "gemini-answers",
            "--config",
            "/app/config.json",
            "--answers-out",
            "/app/out/answers_gemini.json",
        )
        if model:
            cmd.extend(["--model", model])
        return cmd
    if action == "dry-run":
        return docker_run_cmd("submit", "--config", "/app/config.json", "--dry-run")
    if action == "submit":
        return docker_run_cmd("submit", "--config", "/app/config.json")
    raise ValueError(f"Acción no permitida: {action}")


def run_make_action(action: str, model: str | None = None) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Acción no permitida: {action}")

    cmd = build_action_cmd(action, model)
    stdin: str | None = None
    if action == "submit":
        cfg = load_config_file()
        if cfg.get("confirm_submit", True):
            stdin = "s\n"

    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            input=stdin,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as err:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": (err.stdout or "") if isinstance(err.stdout, str) else "",
            "stderr": (err.stderr or "") if isinstance(err.stderr, str) else "",
            "error": f"Tiempo agotado ({RUN_TIMEOUT}s).",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": "No se encontró docker. ¿Está Docker Desktop en marcha?",
        }

    payload: dict[str, Any] = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": " ".join(cmd),
    }

    if action == "gemini" and proc.returncode == 0 and OUT_GEMINI.is_file():
        answers = read_answers_file(OUT_GEMINI)
        payload["answers"] = answers
        existing = load_config_file()
        existing["answers"] = answers
        write_config(existing)
        payload["config_saved"] = True

    return payload


class ConfigUIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[config-ui] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._serve_html()
            elif path == "/api/config":
                self._send_json(200, load_config_file())
            elif path == "/api/import/gemini":
                self._send_json(200, read_answers_file(OUT_GEMINI))
            elif path == "/api/import/retake":
                self._send_json(200, read_answers_file(OUT_RETAKE))
            else:
                self._send_json(404, {"error": "No encontrado"})
        except FileNotFoundError as err:
            self._send_json(404, {"error": str(err)})
        except (json.JSONDecodeError, ValueError) as err:
            self._send_json(400, {"error": str(err)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/config":
                self._post_config()
            elif path.startswith("/api/run/"):
                action = path.removeprefix("/api/run/").strip("/")
                body = self._read_json_body()
                model = body.get("model") if isinstance(body, dict) else None
                if model is not None and not isinstance(model, str):
                    raise ValueError("model debe ser texto.")
                model = model.strip() if model else None
                if isinstance(body, dict) and body.get("config"):
                    existing = load_config_file() if CONFIG_PATH.is_file() else {}
                    merged = merge_for_save(existing, body["config"])
                    write_config(merged)
                result = run_make_action(action, model or None)
                status = 200 if result.get("ok") else 500
                self._send_json(status, result)
            else:
                self._send_json(404, {"error": "No encontrado"})
        except (json.JSONDecodeError, ValueError, TypeError) as err:
            self._send_json(400, {"error": str(err)})

    def _post_config(self) -> None:
        submitted = self._read_json_body()
        if not isinstance(submitted, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON.")
        existing = load_config_file() if CONFIG_PATH.is_file() else {}
        merged = merge_for_save(existing, submitted)
        write_config(merged)
        self._send_json(200, {"ok": True, "path": str(CONFIG_PATH)})

    def _serve_html(self) -> None:
        if not HTML_PATH.is_file():
            self._send_json(500, {"error": f"Falta {HTML_PATH.name}"})
            return
        body = HTML_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Editor web local de config.json")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto (defecto: 8765)")
    parser.add_argument("--open", action="store_true", help="Abrir el navegador al iniciar")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ConfigUIHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Editor de config: {url}")
    print(f"Escribe en: {CONFIG_PATH}")
    print("Puede ejecutar gemini / submit vía Docker desde el navegador.")
    print("Ctrl+C para detener.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
