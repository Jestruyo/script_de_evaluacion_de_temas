# Cliente de cuestionarios Moodle (campus UNIR Colombia)

Herramienta en Python que reproduce el flujo de un intento de **test en Moodle** (`mod/quiz`): descarga la página del intento, opcionalmente guarda un snapshot JSON y puede enviar las respuestas definidas en un archivo de configuración.

## Los tres comandos principales

Úsalos en este orden: ver el cuestionario, simular el envío y entregar.

| Paso | Comando (Python local) | Comando (Docker) |
|------|------------------------|-------------------|
| **1. Ver preguntas** | `python moodle_quiz.py fetch --config config.json` | `docker compose run --rm moodle-quiz fetch --config /app/config.json` |
| **2. Probar sin enviar** | `python moodle_quiz.py submit --config config.json --dry-run` | `docker compose run --rm -it moodle-quiz submit --config /app/config.json --dry-run` |
| **3. Enviar al campus** | `python moodle_quiz.py submit --config config.json` | `docker compose run --rm -it moodle-quiz submit --config /app/config.json` |

Antes de ejecutarlos necesitas `config.json` con `attempt`, `cmid`, `answers` y sesión (`cookie` o `MOODLE_QUIZ_COOKIE`). La primera vez con Docker: `docker compose build`. En el paso 3, si `confirm_submit` es `true`, el script pregunta en consola; por eso Docker usa `-it` en `submit`. Con `"confirm_submit": false` puedes quitar `-it`.

## Requisitos

- Python 3.10+ (entorno local) **o** Docker con Docker Compose
- Una sesión válida en el campus (cookies de navegador)
- `attempt` y `cmid` correctos para el intento abierto del cuestionario

## Instalación local

```bash
cd script_de_evaluacion_de_temas
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Ollama (opcional, para `ollama-answers`)

Sirve para generar el objeto `answers` con un modelo **local** (sin API de pago). No va incluido en el contenedor Docker por defecto; úsalo en tu máquina con Python.

1. **Instala Ollama** (macOS):
   - Desde [ollama.com](https://ollama.com/download) (app), o con Homebrew: `brew install ollama`
   - Inicia el servicio (la app lo hace, o en terminal: `ollama serve`).

2. **Descarga un modelo** (ejemplo ligero; elige otro si prefieres):

   ```bash
   ollama pull llama3.2
   ```

3. **Genera las respuestas** (misma `cookie` / intento que para `fetch`; no hace falta tener `answers` rellenado aún):

   ```bash
   python moodle_quiz.py ollama-answers --config config.json --answers-out answers_ollama.json
   ```

   El comando imprime un JSON y opcionalmente lo guarda. Copia ese bloque dentro de `config.json` → `"answers"`, revisa los índices y luego usa `submit` como siempre.

Parámetros opcionales: `--ollama-url http://127.0.0.1:11434`, `--model llama3.2`. También puedes poner en `config.json` un objeto `"ollama": { "base_url": "...", "model": "..." }`.

**Docker:** Ollama en el host Mac se suele exponer con `--ollama-url http://host.docker.internal:11434` al ejecutar el contenedor (el servicio debe estar escuchando en tu PC).

El modelo **puede equivocarse**; revisa siempre el JSON antes de `submit`. Usar IA para evaluaciones puede ir contra las normas del curso.

## Archivo de configuración

Crea `config.json` en la raíz del proyecto (está en `.gitignore`; no lo subas a repositorios públicos).

| Campo | Descripción |
|--------|-------------|
| `base_url` | Origen del campus, p. ej. `https://campusvirtual.colombia.unir.net` |
| `attempt` | Número del intento (query `attempt=` en la URL de `attempt.php`) |
| `cmid` | ID de la actividad del curso (query `cmid=` en la misma URL) |
| `cookie` | Cadena del header HTTP **`Cookie:`** tal como la muestra el navegador (ver abajo). Puede ir vacía si usas `MOODLE_QUIZ_COOKIE`. |
| `answers` | Objeto: clave = número de pregunta (`"1"` … `"N"`), valor = **índice** de opción: `0` = a, `1` = b, `2` = c, `3` = d |
| `finish_attempt` | Si es `true`, el primer POST incluye “Terminar intento…” (sale de `attempt.php`; suele redirigir a `summary.php`) |
| `finalize_after_summary` | Si es `true` (defecto), y la URL tras el primer POST es `summary.php`, se envía un **segundo** POST con el formulario “Enviar todo y terminar” (`finishattempt=1`). Sin esto el intento puede quedar solo guardado, no entregado |
| `next_finish` | (Opcional) Cadena **exacta** del campo `next` al pulsar “Terminar intento…” (cópiala de DevTools → POST `processattempt` → form data → `next`). Solo si el campus usa un texto distinto al que detecta el script |
| `confirm_submit` | Si es `true`, `submit` pide confirmación en consola. Pon `false` para automatización o Docker sin `-it` |
| `ollama` | (Opcional) Para `ollama-answers`: `{"base_url": "http://127.0.0.1:11434", "model": "llama3.2"}` |

Ejemplo de estructura (valores ilustrativos):

```json
{
  "base_url": "https://campusvirtual.colombia.unir.net",
  "attempt": 7574026,
  "cmid": 572606,
  "cookie": "MoodleSessionCO=…; UNIR_SESSION=…; …",
  "answers": {
    "1": 0,
    "2": 1,
    "3": 2
  },
  "finish_attempt": true,
  "finalize_after_summary": true,
  "confirm_submit": true
}
```

### Flujo HTTP que reproduce el navegador

1. **GET** `mod/quiz/attempt.php?attempt=…&cmid=…` — página del intento con preguntas y campos ocultos (`sesskey`, `sequencecheck`, etc.).
2. **POST** `mod/quiz/processattempt.php?cmid=…` — respuestas (`q…_answer`), navegación (`next` = “Terminar intento…”, `nextpage=-1`, `slots`, …). Moodle responde a menudo **303** y redirige a **resumen** o revisión.
3. **GET** `mod/quiz/summary.php?attempt=…&cmid=…` — tabla “Respuesta guardada” y el botón **Enviar todo y terminar**. El intento puede seguir **abierto** hasta el paso siguiente.
4. **POST** otra vez `mod/quiz/processattempt.php` con el formulario del resumen (`finishattempt=1`, `attempt`, `cmid`, `sesskey`, `timeup`, `slots`) — cierre definitivo del intento (luego suele ir a `review.php` o similar).

El script hace automáticamente el paso 4 cuando `finish_attempt` y `finalize_after_summary` son `true` y la respuesta al paso 2 apunta a `summary.php`.

### Cómo obtener la cookie

1. Inicia sesión en el campus y abre el cuestionario con el intento activo.
2. Abre DevTools → pestaña **Network**.
3. Recarga o selecciona la petición **GET** a `.../mod/quiz/attempt.php?attempt=...&cmid=...`.
4. En **Request Headers**, copia el valor completo de **`cookie:`** (una línea con muchos `nombre=valor` separados por `;`).

En UNIR Colombia suelen aparecer, entre otras, **`MoodleSessionCO`** y **`UNIR_SESSION`**. No basta con copiar una sola cookie desde la pestaña Application si el campus espera varias.

### Cookie por variable de entorno (recomendado)

Así evitas guardar la sesión en un archivo:

```bash
export MOODLE_QUIZ_COOKIE='nombre=valor; nombre2=valor2; …'
python moodle_quiz.py fetch --config config.json
```

Si `MOODLE_QUIZ_COOKIE` está definida y no vacía, **tiene prioridad** sobre el campo `cookie` del JSON.

## Comandos del script (referencia)

Todos aceptan `-c` / `--config` con la ruta al JSON (por defecto `config.json`). Los **tres comandos imprescindibles** están en la sección anterior; aquí el resto de variantes.

| Comando | Acción |
|---------|--------|
| `fetch` | Descarga el intento e imprime preguntas/opciones; opcionalmente `--snapshot archivo.json` |
| `submit --dry-run` | Construye el mismo POST que `submit` pero **no** lo envía |
| `submit` | Envía las respuestas de `answers` (y el cierre en dos pasos si aplica) |
| `ollama-answers` | Descarga el intento y pide a **Ollama** (local) un índice por pregunta; imprime JSON para `"answers"` |
| `run` | Hace `fetch` (guarda `quiz_snapshot.json`) y luego `submit` en un solo paso |

Ejemplos extra:

```bash
python moodle_quiz.py fetch -c config.json --snapshot ./backup.json
python moodle_quiz.py run --dry-run
python moodle_quiz.py run -c config.json
```

## Flujo de trabajo recomendado

1. **Configura** `attempt`, `cmid` y sesión (`cookie` o `MOODLE_QUIZ_COOKIE`).
2. Ejecuta **`fetch`** y revisa en consola que el número de preguntas y los textos coinciden con lo que ves en el navegador.
3. Completa **`answers`** con los índices correctos (comprueba contra la lista `[0] a.`, `[1] b.`, etc.).
4. Ejecuta **`submit --dry-run`** y confirma que el resumen “Payload de respuestas” es el deseado.
5. Ejecuta **`submit`** (o **`run`**). Si `confirm_submit` es `true`, escribe `s` cuando pregunte.

Tras un envío correcto, el script suele indicar redirección a `summary.php` o `review.php`.

## Uso con Docker

Mismos tres comandos que en la tabla superior, usando `--config /app/config.json`. Construye la imagen la primera vez:

```bash
docker compose build
```

- `docker-compose.yml` monta `./config.json` en `/app/config.json`. El `Dockerfile` usa por defecto `fetch` con ese archivo.
- Para **confirmación interactiva** en `submit`, usa **`-it`**. Si usas `confirm_submit: false`, no hace falta.
- El snapshot por defecto se escribe **dentro del contenedor**; con `--rm` se pierde al salir. Para guardarlo en tu máquina:
  1. Crea una carpeta, p. ej. `out/`.
  2. En `docker-compose.yml` descomenta el volumen `./out:/app/out`.
  3. Ejecuta:  
     `docker compose run --rm moodle-quiz fetch --config /app/config.json --snapshot /app/out/quiz_snapshot.json`
- Puedes pasar la cookie al contenedor sin meterla en el archivo:  
  `MOODLE_QUIZ_COOKIE='…' docker compose run --rm -e MOODLE_QUIZ_COOKIE moodle-quiz fetch --config /app/config.json`

## Solución de problemas

| Síntoma | Qué revisar |
|---------|-------------|
| `No se pudo parsear "cookie"` / texto `PEGA_AQUI...` | Sustituye `cookie` por la cadena real del header `cookie:` o usa `MOODLE_QUIZ_COOKIE`. |
| `HTTP 404` en `POST` a `processattempt.php` | Asegúrate de tener la última versión del script (copia todos los campos del formulario, no solo `input[type=hidden]`). Comprueba que el intento siga abierto en el navegador. Si persiste, mira el recorte del cuerpo que imprime el script (p. ej. Akamai). |
| Redirige al login | Cookie incompleta o expirada. |
| `submit` no avanza en Docker | Añade `-it` o pon `"confirm_submit": false`. |

## Aviso de uso responsable

Este proyecto automatiza peticiones HTTP equivalentes a usar el navegador. Úsalo solo donde la normativa del curso y del campus lo permitan. El envío automático de evaluaciones puede infringir reglas académicas; la responsabilidad es tuya.
