#!/usr/bin/env python3
"""
Cliente para cuestionarios Moodle (mod_quiz) en campusvirtual UNIR Colombia.

Uso:
  python moodle_quiz.py fetch [--config PATH]
  python moodle_quiz.py submit [--config PATH]
  python moodle_quiz.py run [--config PATH]

Las respuestas van en config.json -> "answers".
La cookie: copia el valor del header "cookie:" (Network → attempt.php) en "cookie",
o define la variable de entorno MOODLE_QUIZ_COOKIE (recomendado para no guardarla en disco).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

DEFAULT_BASE = "https://campusvirtual.colombia.unir.net"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'


# Texto del botón «Terminar intento» en Moodle (es): suele usar elipsis Unicode …
# Si no se detecta en el HTML, se prueba este y el fallback en build_payload.
FINISH_NEXT_FALLBACKS = (
    "Terminar intento\u2026",  # U+2026 (típico en traducciones Moodle)
    "Terminar intento...",
)


@dataclass
class Question:
    slot: int
    qno: int
    field_prefix: str
    text: str
    options: list[str] = field(default_factory=list)
    sequence_value: str = "1"

    @property
    def answer_field(self) -> str:
        return f"{self.field_prefix}_answer"


@dataclass
class QuizAttempt:
    attempt_id: int
    cmid: int
    sesskey: str
    questions: list[Question]
    hidden_fields: dict[str, str]
    process_url: str
    raw_html: str = ""
    next_finish_value: str | None = None  # valor exacto del botón name="next" al terminar


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_cookie_header(cookie: str) -> dict[str, str]:
    jar: dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        jar[name.strip()] = value.strip()
    return jar


def normalize_cookie_header(cookie: str) -> str:
    """Quita espacios extremos y saltos típicos al pegar desde DevTools."""
    return " ".join(cookie.strip().split())


def cookie_from_config(config: dict[str, Any]) -> str:
    env = os.environ.get("MOODLE_QUIZ_COOKIE", "").strip()
    if env:
        return env
    return str(config.get("cookie", "") or "").strip()


def make_session(cookie: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    raw = normalize_cookie_header(cookie or "")
    if not raw:
        raise ValueError(
            'El campo "cookie" está vacío. Opciones: '
            '(1) Pega en config.json el valor completo del header "cookie:" de Chrome '
            "(Network → la petición a attempt.php → Request Headers); "
            "(2) exporta MOODLE_QUIZ_COOKIE='nombre=valor; ...' antes de ejecutar."
        )
    if "PEGA_AQUI" in raw.upper():
        raise ValueError(
            "La cookie sigue siendo el texto de ejemplo del config.example.json. "
            'Sustituye "cookie" por la cadena real del navegador (con varios nombre=valor; separados por ;). '
            "Ejemplo esperado contiene '=': MoodleSessionCO=abcd…; UNIR_SESSION=xy…"
        )
    jar = parse_cookie_header(raw)
    if not jar:
        raise ValueError(
            'No se pudo parsear "cookie". Debe tener al menos un par nombre=valor. '
            "Copia desde DevTools → Network → GET attempt.php → Request Headers "
            '(no uses el valor de "_comment_cookie" ni pegues sólo parte).'
            f" Recibido ({len(raw)} caracteres): {raw[:120]}{'...' if len(raw) > 120 else ''}"
        )
    for name, value in jar.items():
        session.cookies.set(name, value)
    return session


def _headers_attempt_get(base_url: str, cmid: int) -> dict[str, str]:
    root = base_url.rstrip("/")
    return {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "es-CO,es-419;q=0.9,es;q=0.8",
        "Cache-Control": "max-age=0",
        "Referer": f"{root}/mod/quiz/view.php?id={cmid}",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }


def _headers_post_processattempt(base_url: str, referer: str) -> dict[str, str]:
    root = base_url.rstrip("/")
    return {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "es-CO,es-419;q=0.9,es;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": root,
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }


def _headers_submit_post(base_url: str, quiz: QuizAttempt) -> dict[str, str]:
    root = base_url.rstrip("/")
    q = urlencode({"attempt": quiz.attempt_id, "cmid": quiz.cmid})
    return _headers_post_processattempt(
        base_url, f"{root}/mod/quiz/attempt.php?{q}"
    )


def clean_text(element) -> str:
    if element is None:
        return ""
    return re.sub(r"\s+", " ", element.get_text(separator=" ", strip=True))


def _extract_moodle_error_message(html: str) -> str | None:
    """Intenta obtener el texto útil de una página moodle_exception / error."""
    soup = BeautifulSoup(html, "lxml")
    for sel in (
        ".alert-danger",
        ".notifyproblem",
        ".errorboxmessage",
        "#notice .boxaligncenter",
        "div[role='alert']",
        ".box.generalbox",
    ):
        el = soup.select_one(sel)
        if el:
            t = clean_text(el)
            if t and len(t) > 20:
                return t[:900]
    return None


def _print_http_diagnostic(resp: requests.Response) -> None:
    print(f"\nHTTP {resp.status_code} desde {resp.url}", file=sys.stderr)
    moodle_err = _extract_moodle_error_message(resp.text)
    if moodle_err:
        print("\nMensaje en la página de error de Moodle:", file=sys.stderr)
        print(moodle_err, file=sys.stderr)
    snippet = re.sub(r"\s+", " ", resp.text.strip())
    if len(snippet) > 1500:
        snippet = snippet[:1500] + " ..."
    print("Recorte del cuerpo (si Akamai/HTML de error está vacío verás pocas líneas):", file=sys.stderr)
    print(snippet if snippet else "(cuerpo vacío)", file=sys.stderr)
    print(
        "\nPistas: vuelve a copiar la cabecera Cookie completa desde Network;"
        " prueba ejecutar igual sin Docker (python moodle_quiz.py fetch)."
        " Un 403/404 con cuerpo mínimo puede ser WAF Akamai; un 404 tras POST"
        " a veces indica POST incompleto (actualiza el script) o intento ya cerrado.",
        file=sys.stderr,
    )


def extract_sesskey(soup: BeautifulSoup, html: str) -> str:
    for tag in soup.select('input[name="sesskey"]'):
        if tag.get("value"):
            return tag["value"]
    match = re.search(r'"sesskey"\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1)
    raise ValueError("No se encontró sesskey en la página (¿sesión expirada?)")


def parse_questions(soup: BeautifulSoup) -> list[Question]:
    questions: list[Question] = []
    for block in soup.select("div.que"):
        qno_el = block.select_one(".qno")
        if not qno_el:
            continue
        try:
            qno = int(qno_el.get_text(strip=True))
        except ValueError:
            continue

        seq = block.select_one('input[name$="_:sequencecheck"]')
        if not seq or not seq.get("name"):
            continue
        prefix = seq["name"].replace("_:sequencecheck", "")

        qtext_el = block.select_one(".qtext")
        text = clean_text(qtext_el)

        options: list[str] = []
        for row in block.select(".answer > div[class^='r']"):
            label = row.select_one("[data-region='answer-label'] .flex-fill, .flex-fill")
            if label:
                options.append(clean_text(label))

        slot_match = re.search(r"question-\d+-(\d+)", block.get("id", ""))
        slot = int(slot_match.group(1)) if slot_match else qno

        seq_val = (seq.get("value") or "1").strip()

        questions.append(
            Question(
                slot=slot,
                qno=qno,
                field_prefix=prefix,
                text=text,
                options=options,
                sequence_value=seq_val,
            )
        )

    questions.sort(key=lambda q: q.qno)
    return questions


def _resolve_attempt_form_action(base_url: str, action: str) -> str:
    """action del formulario attempt puede ser absoluta, protocolo-relativa o relativa."""
    a = (action or "").strip()
    root = base_url.rstrip("/")
    if not a:
        return f"{root}/mod/quiz/processattempt.php"
    if a.startswith(("http://", "https://")):
        return a
    if a.startswith("//"):
        p = urlparse(root)
        return f"{p.scheme}:{a}"
    if a.startswith("/"):
        return root + a
    return f"{root}/{a.lstrip('/')}"


def extract_finish_next_from_form(form) -> str | None:
    """Valor exacto enviado en next= al pulsar «Terminar intento» (idioma / elipsis)."""
    for el in form.select('input[name="next"], button[name="next"]'):
        val = (el.get("value") or "").strip()
        if not val:
            val = clean_text(el)
        if not val:
            continue
        low = val.lower()
        if "terminar" in low and "intento" in low:
            return val
    return None


def _collect_responseform_inputs(form) -> dict[str, str]:
    """
    Campos no visibles del intento. No usar solo input[type=hidden]: en HTML5 el
    tipo por defecto es text y algunos `cmid`/`attempt` vienen sin type=hidden.
    """
    hidden: dict[str, str] = {}
    for inp in form.select("input"):
        name = inp.get("name")
        if not name or name.endswith("_:sequencecheck"):
            continue
        t = (inp.get("type") or "").lower()
        if t in ("submit", "button", "image", "reset"):
            continue
        if t == "radio":
            continue
        if "_answer" in name:
            continue
        hidden[name] = inp.get("value") or ""
    return hidden


def parse_attempt_page(html: str, attempt: int, cmid: int, base_url: str) -> QuizAttempt:
    soup = BeautifulSoup(html, "lxml")
    sesskey = extract_sesskey(soup, html)

    form = soup.select_one("form#responseform")
    if not form:
        raise ValueError("No se encontró el formulario #responseform")

    action = _resolve_attempt_form_action(base_url, form.get("action", "") or "")

    hidden = _collect_responseform_inputs(form)

    finish_next = extract_finish_next_from_form(form)

    questions = parse_questions(soup)
    if not questions:
        raise ValueError("No se detectaron preguntas en la página")

    return QuizAttempt(
        attempt_id=attempt,
        cmid=cmid,
        sesskey=sesskey,
        questions=questions,
        hidden_fields=hidden,
        process_url=action,
        raw_html=html,
        next_finish_value=finish_next,
    )


def fetch_attempt(
    session: requests.Session, base_url: str, attempt: int, cmid: int
) -> QuizAttempt:
    url = f"{base_url.rstrip('/')}/mod/quiz/attempt.php"
    params = {"attempt": attempt, "cmid": cmid}
    resp = session.get(
        url,
        params=params,
        headers=_headers_attempt_get(base_url, cmid),
        timeout=60,
    )
    if not resp.ok:
        _print_http_diagnostic(resp)

    resp.raise_for_status()

    if "login" in resp.url.lower() or "login/index.php" in resp.text:
        raise PermissionError(
            "Redirigió al login. Actualiza la cookie (p. ej. MoodleSessionCO, UNIR_SESSION) "
            "en config.json copiando el header Cookie completo desde DevTools."
        )

    return parse_attempt_page(resp.text, attempt, cmid, base_url)


def build_payload(
    quiz: QuizAttempt,
    answers: dict[str, int],
    finish: bool,
) -> dict[str, str]:
    payload: dict[str, str] = dict(quiz.hidden_fields)
    payload["sesskey"] = quiz.sesskey
    payload["attempt"] = str(quiz.attempt_id)

    for q in quiz.questions:
        key = str(q.qno)
        if key not in answers:
            raise KeyError(
                f"Falta respuesta para pregunta {q.qno} en config (clave '{key}')"
            )
        choice = answers[key]
        if choice < 0 or choice >= len(q.options):
            raise ValueError(
                f"Pregunta {q.qno}: índice {choice} fuera de rango "
                f"(0..{len(q.options) - 1})"
            )
        payload[q.answer_field] = str(choice)
        payload[f"{q.field_prefix}_:sequencecheck"] = q.sequence_value
        payload[f"{q.field_prefix}_:flagged"] = "0"

    payload.setdefault("cmid", str(quiz.cmid))
    payload.setdefault("thispage", "0")
    slots_csv = ",".join(
        str(q.slot) for q in sorted(quiz.questions, key=lambda x: x.qno)
    )
    if not payload.get("slots"):
        payload["slots"] = slots_csv

    if finish:
        payload["next"] = (
            quiz.next_finish_value
            if quiz.next_finish_value
            else FINISH_NEXT_FALLBACKS[0]
        )
        payload["nextpage"] = "-1"
    else:
        payload["nextpage"] = payload.get("nextpage", "0")

    payload.setdefault("timeup", "0")
    payload.setdefault("scrollpos", "")
    return payload


def _merge_query_into_payload(
    process_url: str, payload: dict[str, str]
) -> tuple[str, dict[str, str]]:
    """
    POST con el mismo cuerpo que el navegador: parámetros del action (?cmid=) también
    en el formulario; la URL del POST sin query string (evita edge cases en proxies).
    """
    parsed = urlparse(process_url)
    merged = dict(payload)
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        merged.setdefault(k, v)
    path_only = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return path_only, merged


def submit_attempt(
    session: requests.Session,
    quiz: QuizAttempt,
    payload: dict[str, str],
    base_url: str = DEFAULT_BASE,
) -> requests.Response:
    headers = _headers_submit_post(base_url, quiz)
    post_url, data = _merge_query_into_payload(quiz.process_url, payload)
    return session.post(
        post_url,
        data=data,
        headers=headers,
        timeout=60,
        allow_redirects=True,
    )


def resolve_form_action(base_url: str, action: str | None) -> str:
    """Convierte action relativa/absoluta del <form> en URL completa."""
    raw = (action or "").strip()
    root = base_url.rstrip("/")
    if not raw:
        return f"{root}/mod/quiz/processattempt.php"
    if raw.startswith("http"):
        return raw
    if raw.startswith("/"):
        return root + raw
    return f"{root}/{raw.lstrip('/')}"


def post_finish_form_from_summary(
    session: requests.Session,
    base_url: str,
    summary_resp: requests.Response,
) -> requests.Response | None:
    """
    Tras pedir «Terminar intento», Moodle puede mostrar summary.php con otro POST
    («Enviar todo y terminar», formulario #frm-finishattempt). Sin este paso el
    intento puede seguir abierto.
    """
    if "summary.php" not in summary_resp.url:
        return None
    soup = BeautifulSoup(summary_resp.text, "lxml")
    form = soup.select_one("form#frm-finishattempt")
    if not form:
        return None
    process_url = resolve_form_action(base_url, form.get("action"))
    payload: dict[str, str] = {}
    for inp in form.select("input[name]"):
        name = inp.get("name")
        if name:
            payload[name] = inp.get("value") or ""
    if not payload:
        return None
    headers = _headers_post_processattempt(base_url, summary_resp.url)
    return session.post(
        process_url,
        data=payload,
        headers=headers,
        timeout=60,
        allow_redirects=True,
    )


def print_questions(quiz: QuizAttempt) -> None:
    print(f"Intento: {quiz.attempt_id} | cmid: {quiz.cmid} | sesskey: {quiz.sesskey}")
    if quiz.next_finish_value:
        print(f"Botón «Terminar intento» detectado (next): {quiz.next_finish_value!r}")
    print(f"Preguntas: {len(quiz.questions)}\n")
    for q in quiz.questions:
        print(f"--- Pregunta {q.qno} (slot {q.slot}) ---")
        print(f"Campo: {q.answer_field}")
        print(q.text[:300] + ("..." if len(q.text) > 300 else ""))
        for i, opt in enumerate(q.options):
            letter = chr(ord("a") + i)
            print(f"  [{i}] {letter}. {opt}")
        print()


def save_snapshot(quiz: QuizAttempt, path: Path) -> None:
    data = {
        "attempt": quiz.attempt_id,
        "cmid": quiz.cmid,
        "sesskey": quiz.sesskey,
        "process_url": quiz.process_url,
        "next_finish_value": quiz.next_finish_value,
        "questions": [
            {
                "qno": q.qno,
                "slot": q.slot,
                "field_prefix": q.field_prefix,
                "answer_field": q.answer_field,
                "sequence_value": q.sequence_value,
                "text": q.text,
                "options": q.options,
            }
            for q in quiz.questions
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_fetch(config: dict[str, Any], snapshot: Path | None) -> int:
    base = config.get("base_url", DEFAULT_BASE)
    session = make_session(cookie_from_config(config))
    quiz = fetch_attempt(session, base, config["attempt"], config["cmid"])
    print_questions(quiz)
    if snapshot:
        save_snapshot(quiz, snapshot)
        print(f"Snapshot guardado en {snapshot}")
    return 0


def cmd_submit(config: dict[str, Any], dry_run: bool) -> int:
    base = config.get("base_url", DEFAULT_BASE)
    session = make_session(cookie_from_config(config))
    quiz = fetch_attempt(session, base, config["attempt"], config["cmid"])
    override_next = (config.get("next_finish") or "").strip()
    if override_next:
        quiz = replace(quiz, next_finish_value=override_next)

    answers_raw = config.get("answers", {})
    answers = {str(k): int(v) for k, v in answers_raw.items()}
    finish = bool(config.get("finish_attempt", True))

    payload = build_payload(quiz, answers, finish)
    print_questions(quiz)
    print("Payload de respuestas:")
    for q in quiz.questions:
        idx = answers[str(q.qno)]
        label = quiz.questions[q.qno - 1].options[idx] if idx < len(q.options) else "?"
        print(f"  P{q.qno} -> [{idx}] {label[:80]}")

    if dry_run:
        print("\n[dry-run] No se envió el formulario.")
        if finish and config.get("finalize_after_summary", True):
            print(
                "[dry-run] Tras el primer POST, si la respuesta es summary.php, el script "
                "enviaría el segundo POST (#frm-finishattempt, «Enviar todo y terminar»)."
            )
        return 0

    confirm = config.get("confirm_submit", True)
    if confirm:
        reply = input("\n¿Enviar respuestas al campus? [s/N]: ").strip().lower()
        if reply not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            return 1

    resp = submit_attempt(session, quiz, payload, base)
    print(f"\n1) Primer POST | HTTP {resp.status_code} | URL: {resp.url}")

    if not resp.ok:
        _print_http_diagnostic(resp)
        print(
            "\nEl POST no tuvo éxito (4xx/5xx). Revisa el recorte del cuerpo arriba; "
            "suele faltar `cmid`/`slots`/`thispage` o la sesión caducó.",
            file=sys.stderr,
        )
        return 1

    finalize = bool(config.get("finalize_after_summary", True))
    if finish and finalize and "summary.php" in resp.url:
        print(
            "\n2) Página de resumen detectada: enviando «Enviar todo y terminar» "
            "(formulario #frm-finishattempt)…"
        )
        resp2 = post_finish_form_from_summary(session, base, resp)
        if resp2 is not None:
            resp = resp2
            print(
                f"   HTTP {resp.status_code} | URL: {resp.url}"
            )
        else:
            print(
                "   No se encontró #frm-finishattempt en el HTML. "
                "El intento podría estar ya cerrado o el tema usar otra plantilla."
            )

    if "review.php" in resp.url:
        print("\nParece que el intento quedó entregado (página de revisión).")
    elif "summary.php" in resp.url:
        if finish and not finalize:
            print(
                "\nSigues en resumen: confirma manualmente «Enviar todo y terminar» "
                "o pon `finalize_after_summary`: true en el config."
            )
        else:
            print(
                "\nSigues en resumen: revisa la sesión o si el segundo POST fue rechazado "
                "(403, WAF, etc.)."
            )
    elif "attempt.php" in resp.url:
        print("\nSigue en attempt.php: revisa errores o respuestas incompletas.")
    elif "processattempt" in resp.url:
        print(
            "\nRespuesta inesperada en processattempt.php. Si viste 404 antes, "
            "actualiza el script (campos del form) y vuelve a probar.",
        )
    else:
        print("\nRevisa la URL final en el navegador con la misma sesión.")

    return 0


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("config.json"),
        help="Ruta a config.json",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente Moodle quiz UNIR")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="Descargar y listar preguntas")
    _add_config_arg(p_fetch)
    p_fetch.add_argument(
        "--snapshot",
        type=Path,
        default=Path("quiz_snapshot.json"),
        help="Guardar JSON con preguntas parseadas",
    )

    p_submit = sub.add_parser("submit", help="Enviar respuestas del config")
    _add_config_arg(p_submit)
    p_submit.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se enviaría sin POST",
    )

    p_run = sub.add_parser("run", help="fetch + submit")
    _add_config_arg(p_run)
    p_run.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if not args.config.exists():
        print(f"No existe {args.config}. Copia config.example.json -> config.json", file=sys.stderr)
        return 2

    config = load_config(args.config)

    if args.command == "fetch":
        return cmd_fetch(config, args.snapshot)
    if args.command == "submit":
        return cmd_submit(config, args.dry_run)
    if args.command == "run":
        cmd_fetch(config, Path("quiz_snapshot.json"))
        return cmd_submit(config, args.dry_run)
    return 2


if __name__ == "__main__":
    sys.exit(main())
