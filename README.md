# Cliente de cuestionarios Moodle (campus UNIR Colombia)

Herramienta en Python que reproduce el flujo de un intento de **test en Moodle** (`mod/quiz`): descarga la página del intento, opcionalmente guarda un snapshot JSON y puede enviar las respuestas definidas en un archivo de configuración.

**Guía completa paso a paso (Docker, Google Gemini, primer envío y opcional segundo intento):** [Paso a paso completo](#paso-a-paso-completo).

## Solo Docker (+ Google Gemini)

Enfoque recomendado si **no** quieres instalar Python en el Mac: solo **Docker** (Desktop o Engine + Compose). Las respuestas automáticas usan la **API de Gemini** (modelo por defecto `gemini-2.5-flash`): necesitas una clave de [Google AI Studio](https://aistudio.google.com/) y conexión a Internet en el contenedor.

Los comandos Docker están resumidos en un **`Makefile`** en la raíz del repo: en lugar de copiar líneas largas de `docker compose run …`, usa `make` (ver [Atajos con Make](#atajos-con-make-recomendado)).

1. Clona el repo y coloca `config.json` en la raíz (con `base_url`, `attempt`, `cmid`, `cookie` o usa `MOODLE_QUIZ_COOKIE`).
2. **Construir cliente y primera lectura (misma consola)** — como en **[Paso a paso, apartado 4](#4-reconstruir-la-imagen-y-leer-el-cuestionario-docker)**:
   ```bash
   make build
   make fetch
   ```
3. **Clave de Gemini** (no la subas a Git): crea un `.env` con `GEMINI_API_KEY=…` (`.env` está en `.gitignore`; `docker-compose.yml` ya lo carga con `env_file`). Alternativa: `export GEMINI_API_KEY='…'` en el shell.
4. Genera `answers` con la IA (el contenedor debe poder salir a la API de Google):
   ```bash
   make gemini
   ```
   Abre en tu Mac `./out/answers_gemini.json` y **copia** el JSON al campo `"answers"` de `config.json`.
5. Simula envío: `make dry-run`
6. Entrega: `make submit`  
   (Si `MOODLE_QUIZ_COOKIE` está vacío en el JSON, exporta la cookie en el host antes de cada comando; con `docker compose` manual añade `-e MOODLE_QUIZ_COOKIE`.)

| Variable / detalle | Uso |
|--------------------|-----|
| `GEMINI_API_KEY` | Clave de API de Google AI Studio; ponla en `.env` (recomendado), expórtala en el shell, usa `--api-key` en el comando, o (no recomendado en repos públicos) `"gemini": {"api_key": "…"}` en `config.json`. |
| `GEMINI_MODEL` | (Opcional) Sobrescribe el modelo; por defecto `gemini-2.5-flash` o `gemini.model` en el JSON. Con Make: `make gemini MODEL=gemini-2.0-flash`. |
| Carpeta `out/` | Montada en `./out`; ahí se guardan `answers_gemini.json` y snapshots (`make snapshot` → `out/quiz_snapshot.json`). |

**No necesitas** `python3` en el Mac si sigues solo este flujo (solo Docker).

## Atajos con Make (recomendado)

Desde la raíz del repo (`script_de_evaluacion_de_temas`), con `config.json` listo y `.env` con `GEMINI_API_KEY` si usarás IA:

| Comando | Acción |
|---------|--------|
| `make help` | Lista todos los atajos (target por defecto) |
| `make build` | `docker compose build moodle-quiz` |
| `make fetch` | Ver preguntas del intento actual |
| `make snapshot` | `fetch` + guarda `out/quiz_snapshot.json` |
| `make gemini` | Genera `out/answers_gemini.json` con Gemini |
| `make retake` | Tras entregar: `out/answers_retake.json` (review + Gemini) |
| `make dry-run` | Simula envío sin mandar al campus |
| `make submit` | Entrega el intento al campus |
| `make config-ui` | Editor web local de `config.json` (http://127.0.0.1:8765) |

Opcional: `make gemini MODEL=gemini-2.0-flash` para probar otro modelo.

### Editor web de `config.json`

Si prefieres no editar JSON a mano, abre el formulario local:

```bash
make config-ui
```

Se abre el navegador en **http://127.0.0.1:8765**. Desde ahí puedes:

- Pegar la **URL** de `attempt.php` para rellenar `attempt`, `cmid` y `base_url`
- Pegar la **cookie** de DevTools
- Pulsar **Generar respuestas (Gemini)** — guarda `config.json`, ejecuta Docker (como `make gemini`), muestra el JSON y lo guarda en `answers`
- Pulsar **Simular envío** o **Enviar al campus** — equivalente a `make dry-run` / `make submit` (con confirmación en el navegador)
- Importar manualmente **`out/answers_gemini.json`** o **`out/answers_retake.json`**

El servidor solo escucha en `127.0.0.1` (tu Mac). Necesitas **Docker en marcha** y **`GEMINI_API_KEY` en `.env`** para Gemini. Detén el servidor con **Ctrl+C** en la terminal.

Equivalentes `docker compose` completos siguen documentados más abajo por si prefieres no usar Make.

La guía **ordenada** (incluye primer envío, `retake-answers` y segundo intento) está en [Paso a paso completo](#paso-a-paso-completo).

## Los tres comandos principales

Úsalos en este orden: ver el cuestionario, simular el envío y entregar.

| Paso | Make | Docker (equivalente) | Python local (opcional) |
|------|------|----------------------|-------------------------|
| **1. Ver preguntas** | `make fetch` | `docker compose run --rm moodle-quiz fetch --config /app/config.json` | `python moodle_quiz.py fetch --config config.json` |
| **2. Probar sin enviar** | `make dry-run` | `docker compose run --rm -it moodle-quiz submit --config /app/config.json --dry-run` | `python moodle_quiz.py submit --config config.json --dry-run` |
| **3. Enviar al campus** | `make submit` | `docker compose run --rm -it moodle-quiz submit --config /app/config.json` | `python moodle_quiz.py submit --config config.json` |

Antes de ejecutarlos necesitas `config.json` con `attempt`, `cmid`, `answers` y sesión (`cookie` o `MOODLE_QUIZ_COOKIE`). La primera vez: `make build`. Para **`gemini-answers`** (`make gemini`) necesitas `GEMINI_API_KEY` en `.env` o en el entorno. En el paso 3, si `confirm_submit` es `true`, el script pregunta en consola; por eso Make usa `-it` en `submit`. Con `"confirm_submit": false` puedes quitar `-it`.

## Requisitos

- **Docker** con Docker Compose (flujo principal de este README)
- **Make** (incluido en macOS/Linux; atajos en el `Makefile` del repo)
- **Python 3** en el Mac para `make config-ui` (solo biblioteca estándar; el flujo Docker no lo requiere)
- Python 3.10+ **solo** si ejecutas el script fuera del contenedor
- Una sesión válida en el campus (cookies de navegador)
- `attempt` y `cmid` correctos para el intento abierto del cuestionario

## Instalación local (opcional)

Si no vas a usar el contenedor `moodle-quiz` y prefieres `python` en el host:

```bash
cd script_de_evaluacion_de_temas
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Google Gemini (IA para `gemini-answers` y `retake-answers`)

1. En [Google AI Studio](https://aistudio.google.com/) crea un proyecto/API key si aún no tienes uno.
2. Guarda la clave en `.env` (`GEMINI_API_KEY=…`) o expórtala: `export GEMINI_API_KEY='tu_clave'`.
3. **Docker (Make):**

   ```bash
   make gemini
   ```

   Opcional: `make gemini MODEL=gemini-2.0-flash` (por defecto `gemini-2.5-flash` si no defines `GEMINI_MODEL` ni `gemini.model` en el JSON).

   **Equivalente sin Make:**

   ```bash
   docker compose run --rm -it moodle-quiz gemini-answers --config /app/config.json --answers-out /app/out/answers_gemini.json
   ```

4. **Solo Python en tu máquina** (venv con `pip install -r requirements.txt`):

   ```bash
   export GEMINI_API_KEY='tu_clave'
   python moodle_quiz.py gemini-answers --config config.json --answers-out answers_gemini.json
   ```

El mismo modo por lotes se usa en `retake-answers` cuando hay varias fallidas sin clave en el HTML: **una** consulta con todas esas preguntas pendientes.

Parámetros opcionales: `--api-key`, `--model` / `-m`. En `config.json` puedes usar solo metadatos (sin secretos expuestos), por ejemplo: `"gemini": { "model": "gemini-2.5-flash" }`.

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
| `gemini` | (Opcional) Para `gemini-answers` / `retake-answers`: `{"model": "gemini-2.5-flash"}` y, solo si lo aceptas en tu flujo local, `"api_key": "…"`. Lo más seguro es `GEMINI_API_KEY` en el entorno. |

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

**Docker** (misma variable en el host, se pasa al contenedor):

```bash
export MOODLE_QUIZ_COOKIE='nombre=valor; nombre2=valor2; …'
docker compose run --rm -e MOODLE_QUIZ_COOKIE moodle-quiz fetch --config /app/config.json
```

Si `MOODLE_QUIZ_COOKIE` está definida y no vacía, **tiene prioridad** sobre el campo `cookie` del JSON.

## Comandos del script (referencia)

Todos aceptan `-c` / `--config` con la ruta al JSON (por defecto `config.json`). Los **tres comandos imprescindibles** están en la sección anterior; aquí el resto de variantes.

| Comando | Acción |
|---------|--------|
| `fetch` | Descarga el intento e imprime preguntas/opciones; opcionalmente `--snapshot archivo.json` |
| `submit --dry-run` | Construye el mismo POST que `submit` pero **no** lo envía |
| `submit` | Envía las respuestas de `answers` (y el cierre en dos pasos si aplica) |
| `gemini-answers` | Descarga el intento y envía **todas** las preguntas a Gemini **en una sola** petición; el modelo devuelve un JSON `"answers"` con un índice por pregunta (mejor frente a límites RPM del plan gratuito) |
| `retake-answers` | Con el intento **ya entregado**, descarga `review.php`: conserva las que acertaste; en las fallidas usa la marca correcta del HTML (si existe) o **Gemini**; genera JSON para el **siguiente** intento (`attempt` nuevo en el config) |
| `run` | Hace `fetch` (guarda `quiz_snapshot.json`) y luego `submit` en un solo paso |

Ejemplos extra (host):

```bash
python moodle_quiz.py fetch -c config.json --snapshot ./backup.json
python moodle_quiz.py run --dry-run
python moodle_quiz.py run -c config.json
```

Equivalentes **Make** / **Docker** (`./out` montado en `/app/out`):

```bash
make snapshot          # out/quiz_snapshot.json
make retake            # out/answers_retake.json

# Sin Make:
docker compose run --rm moodle-quiz fetch --config /app/config.json --snapshot /app/out/backup.json
docker compose run --rm -it moodle-quiz run --dry-run
docker compose run --rm -it moodle-quiz run --config /app/config.json
docker compose run --rm -it moodle-quiz retake-answers --config /app/config.json --answers-out /app/out/answers_retake.json
```

### Segundo intento / revisión (`review.php`)

Para la secuencia completa (cuándo cambiar `attempt`, cómo pegar `answers` desde `./out/`, etc.) sigue la sección **[Paso a paso completo](#paso-a-paso-completo)** (apartados **7–9**).

Tras un `submit` exitoso Moodle muestra la revisión (correctas / incorrectas). Comando del script: `retake-answers` (mismas opciones de Gemini que `gemini-answers`: `--api-key`, `--model`). `retake-answers --skip-llm` no consulta el modelo (fallará si falta la clave correcta en el HTML de alguna pregunta fallida).

Usar esto solo donde la normativa del curso lo permita.

## Paso a paso completo

Flujo **solo Docker**: el contenedor lee `/app/config.json` (tu archivo `config.json` en la raíz del repo). Ese archivo va montado **solo lectura**: los JSON generados (`./out/answers_gemini.json`, `./out/answers_retake.json`, …) los abres en el editor y **copias** el contenido en la clave `"answers"` del `config.json` en el Mac.

El bloque **recomendado** (`make build` y `make fetch` en la misma consola) está en el **[apartado 4](#4-reconstruir-la-imagen-y-leer-el-cuestionario-docker)** (tras crear `config.json`).

### Resumen rápido (orden)

| Paso | Apartado doc | Qué haces |
|------|----------------|-----------|
| **0.** | **[1](#1-preparar-el-proyecto-una-vez-por-máquina)** (opcional) | Si usarás IA: `GEMINI_API_KEY` en `.env` o exportada en el shell. |
| **1.** | **[2](#2-en-el-navegador-moodle)** | Intent activo → URL (`attempt`, `cmid`) + **cookie** o `MOODLE_QUIZ_COOKIE`. |
| **2.** | **[3](#3-crear-configjson)** | `config.json`: `base_url`, `attempt`, `cmid`, sesión; `"answers"` puede ser `{}`. |
| **3.** | **[4](#4-reconstruir-la-imagen-y-leer-el-cuestionario-docker)** | **`make build`** + **`make fetch`** |
| **4.** | **[5](#5-obtener-answers-manual-o-con-gemini)** | Manual en JSON o **`make gemini`** → pegas `"answers"` y revisas. |
| **5.** | **[6–7](#6-simular-el-envío-sin-entregar)** | **`make dry-run`** y **`make submit`**. |
| **6.** | **[8](#8-opcional-segundo-intento-con-retake-answers)** (opcional) | Sin cambiar `attempt`, **`make retake`** → pegas `answers_retake` → navegador: **nuevo** intento → **nuevo** `attempt` → de nuevo **[4](#4-reconstruir-la-imagen-y-leer-el-cuestionario-docker)** y `make submit`. |

Tras **`git pull`** o cambiar `moodle_quiz.py`: vuelve a ejecutar **`make build`** (apartado **4**).

Los apartados siguientes detallan cada fase. Variantes con **Python en el PC** se indican donde aplica.

### 1. Preparar el proyecto (una vez por máquina)

**Docker — cliente `moodle-quiz`:** el **`build`** va **junto al `fetch`** en el **[apartado 4](#4-reconstruir-la-imagen-y-leer-el-cuestionario-docker)** (después del `config.json`).

```bash
cd script_de_evaluacion_de_temas

# Si usarás make gemini: GEMINI_API_KEY=… en .env (recomendado; .env está en .gitignore)
# o export GEMINI_API_KEY='…' en esta misma consola.
```

**Solo si no usas Docker** para el cliente:

```bash
cd script_de_evaluacion_de_temas
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. En el navegador (Moodle)

1. Inicia sesión en el campus y entra al cuestionario.
2. Pulsa **Intentar cuestionario** (o reanuda un intento en curso) hasta ver las preguntas.
3. En la **barra de direcciones** copia dos datos de la URL, por ejemplo  
   `.../mod/quiz/attempt.php?attempt=7574026&cmid=572606`  
   - **`attempt`** → `7574026`  
   - **`cmid`** → `572606`
4. Abre **DevTools → Network**, recarga si hace falta, selecciona el **GET** a `attempt.php` y en **Request Headers** copia todo el valor de **`cookie:`** (o usa después `MOODLE_QUIZ_COOKIE`).

Cada **nuevo intento** o **otro test** del curso suele cambiar al menos `attempt` y a veces `cmid`; vuelve a copiar desde la URL activa.

### 3. Crear `config.json`

En la raíz del repo (puedes partir de un JSON vacío de respuestas y rellenar después), o usa **`make config-ui`** para editarlo en el navegador.

```json
{
  "base_url": "https://campusvirtual.colombia.unir.net",
  "attempt": 7574026,
  "cmid": 572606,
  "cookie": "PEGA_AQUI_EL_HEADER_COOKIE_COMPLETO",
  "answers": {},
  "finish_attempt": true,
  "finalize_after_summary": true,
  "confirm_submit": true
}
```

- Si prefieres no guardar la cookie en disco: deja `"cookie": ""` y en terminal `export MOODLE_QUIZ_COOKIE='...'` antes de cada `make fetch` / `make submit` (con `docker compose` manual añade `-e MOODLE_QUIZ_COOKIE`).

### 4. Reconstruir la imagen y leer el cuestionario (Docker)

Desde la raíz (`script_de_evaluacion_de_temas`): reconstruye el servicio **`moodle-quiz`** cuando actualices el repo o `moodle_quiz.py`; en el mismo bloque lanzas **`fetch`** (usa el `config.json` del paso 3).

```bash
cd script_de_evaluacion_de_temas
make build
make fetch
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py fetch --config config.json
```

Debes ver el mismo número de preguntas que en el navegador y textos coherentes.

### 5. Obtener `answers` (manual o con Gemini)

**Opción A — Manual:** edita `config.json` y rellena `"answers"` con índices `0`…`3` según la lista `[0] a.`, `[1] b.`, … del `fetch`.

**Opción B — Gemini desde Docker:** el contenedor necesita salida HTTPS a la API de Google y `GEMINI_API_KEY` en `.env` o en el entorno (no la subas a Git):

```bash
make gemini
```

Abre en tu Mac `./out/answers_gemini.json`, **copia** el objeto y **pégalo** en `"answers"` dentro de `config.json` (sustituye `{}`). Revísalo.

**Opción C — Todo en el PC sin Docker** (Python local + misma variable):

```bash
export GEMINI_API_KEY='tu_clave'
python moodle_quiz.py gemini-answers --config config.json --answers-out answers_gemini.json
```

### 6. Simular el envío (sin entregar)

**Docker (Make):**

```bash
make dry-run
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py submit --config config.json --dry-run
```

Comprueba el bloque “Payload de respuestas”.

### 7. Enviar el primer intento al campus

**Docker (Make):**

```bash
make submit
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py submit --config config.json
```

Si `confirm_submit` es `true`, escribe `s` cuando pregunte. Si todo va bien, acabas en **`review.php`** (revisión) o antes en **`summary.php`**. El número de **`attempt`** que tenías en el config es el del intento **ya entregado**; consérvalo para el paso 8 si vas a usar `retake-answers`.

### 8. (Opcional) Segundo intento con `retake-answers`

Solo si el curso permite **varios intentos** y quieres combinar lo que acertaste con las correcciones de la página de revisión (más Gemini solo donde el HTML no muestre la clave):

1. **No cambies** `attempt` ni `cmid` todavía: deben seguir siendo los del intento que acabas de cerrar (debe coincidir con `review.php?attempt=…&cmid=…`).
2. Ejecuta (con `GEMINI_API_KEY` en `.env` si hace falta consultar Gemini):

   ```bash
   make retake
   ```

3. Copia el contenido de `./out/answers_retake.json` a la clave `"answers"` de `config.json` en el Mac.
4. En el **navegador**, inicia un **nuevo** intento del mismo test (si el botón existe). Al cargar las preguntas, la URL `attempt.php` tendrá un **`attempt` nuevo**.
5. Sustituye en `config.json` ese **`attempt`** (y `cmid` solo si cambiases de actividad). Renueva cookie si caducó.
6. Vuelve a ejecutar: `make fetch` → `make dry-run` → `make submit`.

Si usas `retake-answers --skip-llm`, no se llama a Gemini; el comando fallará si alguna pregunta fallida no muestra en la revisión cuál era la opción correcta.

### 9. Otro cuestionario o tema distinto

Actualiza **`cmid`** y **`attempt`** según la nueva URL de `attempt.php`. Renueva **`cookie`** / `MOODLE_QUIZ_COOKIE` si la sesión caducó. Repite desde el paso **4** (y **5** si generas respuestas con Gemini de nuevo). Si solo cambias de intento del mismo test sin pasar por `retake-answers`, basta con actualizar `attempt` desde la URL y asegurarte de que `"answers"` sigue siendo el que quieres enviar.

## Uso con Docker (detalles)

El flujo principal está al inicio (**Solo Docker (+ Google Gemini)**), en **[Atajos con Make](#atajos-con-make-recomendado)** y en la tabla de **Los tres comandos principales**. Aquí, notas extra:

- El **`Makefile`** envuelve los `docker compose run` habituales; ejecuta `make help` para ver la lista.
- **`make config-ui`** sirve `config-editor.html` y escribe `config.json` en el host (puerto 8765).
- `docker-compose.yml` monta `./config.json` en `/app/config.json` (solo lectura) y `./out` en `/app/out` para `answers_gemini.json` y snapshots. Carga `.env` con `env_file` (p. ej. `GEMINI_API_KEY`). El `Dockerfile` usa por defecto `fetch` con ese archivo.
- Si **actualizas** el repo (`git pull`) o cambias `moodle_quiz.py`, **reconstruye** la imagen: `make build` (si ves `invalid choice: 'retake-answers'`, suele ser que no reconstruiste después de añadir ese comando).
- Para **confirmación interactiva** en `submit`, Make usa **`-it`**. Si usas `confirm_submit: false`, no hace falta.
- Snapshot en el host: `make snapshot` (o el `docker compose run … --snapshot` equivalente).
- Cookie sin guardarla en `config.json`: exporta `MOODLE_QUIZ_COOKIE` en el host antes de `make fetch` / `make submit`; con `docker compose` manual añade `-e MOODLE_QUIZ_COOKIE`.

## Solución de problemas

| Síntoma | Qué revisar |
|---------|-------------|
| `No se pudo parsear "cookie"` / texto `PEGA_AQUI...` | Sustituye `cookie` por la cadena real del header `cookie:` o usa `MOODLE_QUIZ_COOKIE`. |
| `HTTP 404` en `POST` a `processattempt.php` | Asegúrate de tener la última versión del script (copia todos los campos del formulario, no solo `input[type=hidden]`). Comprueba que el intento siga abierto en el navegador. Si persiste, mira el recorte del cuerpo que imprime el script (p. ej. Akamai). |
| Redirige al login | Cookie incompleta o expirada. |
| `submit` no avanza en Docker | Añade `-it` o pon `"confirm_submit": false`. |
| Faltan preguntas en `answers` | Debe existir una clave por cada número de pregunta mostrado en `fetch`. |
| `invalid choice: 'retake-answers'` en Docker | La imagen se construyó con un `moodle_quiz.py` viejo. Ejecuta `make build` y vuelve a lanzar el comando. |

## Aviso de uso responsable

Este proyecto automatiza peticiones HTTP equivalentes a usar el navegador. Úsalo solo donde la normativa del curso y del campus lo permitan. El envío automático de evaluaciones puede infringir reglas académicas; la responsabilidad es tuya.
