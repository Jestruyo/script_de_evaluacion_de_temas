# Cliente de cuestionarios Moodle (campus UNIR Colombia)

Herramienta en Python que reproduce el flujo de un intento de **test en Moodle** (`mod/quiz`): descarga la página del intento, opcionalmente guarda un snapshot JSON y puede enviar las respuestas definidas en un archivo de configuración.

## Solo Docker (+ Ollama en contenedor)

Enfoque recomendado si **no** quieres instalar Python ni Ollama en el Mac: solo **Docker** (Desktop o Engine + Compose).

1. Clona el repo y coloca `config.json` en la raíz (con `base_url`, `attempt`, `cmid`, `cookie` o usa `MOODLE_QUIZ_COOKIE`).
2. Construye la imagen del cliente:  
   `docker compose build`
3. **Ollama en Docker — hay que hacerlo en este orden** (si inviertes los pasos o saltas el `up`, `exec` fallará):
   1. Arranca el servicio (contenedor en marcha):  
      `docker compose up -d ollama`
   2. Con el servicio **running**, descarga el modelo **dentro** del contenedor (primera vez o si cambias de modelo; ~2 GB para `llama3.2`):  
      `docker compose exec ollama ollama pull llama3.2`  
      Si ves `service "ollama" is not running`, el paso anterior no se llegó a ejecutar o el contenedor paró: vuelve a `docker compose up -d ollama` y comprueba con `docker compose ps` que `ollama` esté **Up**.
4. Comprueba el cuestionario:  
   `docker compose run --rm moodle-quiz fetch --config /app/config.json`
5. Genera `answers` con la IA (el compose ya define `OLLAMA_BASE_URL=http://ollama:11434` para el contenedor `moodle-quiz`):  
   `docker compose run --rm -it moodle-quiz ollama-answers --config /app/config.json --answers-out /app/out/answers_ollama.json`  
   Abre en tu Mac `./out/answers_ollama.json` y **copia** el JSON al campo `"answers"` de `config.json`.
6. Simula envío:  
   `docker compose run --rm -it moodle-quiz submit --config /app/config.json --dry-run`
7. Entrega:  
   `docker compose run --rm -it moodle-quiz submit --config /app/config.json`  
   (Si `MOODLE_QUIZ_COOKIE` está vacío en el JSON, puedes exportarla en el host y pasarla:  
   `MOODLE_QUIZ_COOKIE='…' docker compose run --rm -e MOODLE_QUIZ_COOKIE -it moodle-quiz submit --config /app/config.json`)

Parar Ollama y liberar red: `docker compose down` (el volumen `ollama_data` conserva el modelo descargado).

| Variable / detalle | Uso |
|--------------------|-----|
| `OLLAMA_BASE_URL` | Lo define `docker-compose.yml`; el script la usa para `ollama-answers` (prioridad: CLI `--ollama-url` > esta variable > `config.ollama.base_url`). |
| Carpeta `out/` | Montada en `./out`; ahí se guardan `answers_ollama.json` y snapshots si usas `--snapshot /app/out/...`. |

**No necesitas** `python3` ni `brew install ollama` en el Mac si sigues solo este flujo.

## Los tres comandos principales

Úsalos en este orden: ver el cuestionario, simular el envío y entregar.

| Paso | Comando (Docker) | Comando (Python local, opcional) |
|------|------------------|-----------------------------------|
| **1. Ver preguntas** | `docker compose run --rm moodle-quiz fetch --config /app/config.json` | `python moodle_quiz.py fetch --config config.json` |
| **2. Probar sin enviar** | `docker compose run --rm -it moodle-quiz submit --config /app/config.json --dry-run` | `python moodle_quiz.py submit --config config.json --dry-run` |
| **3. Enviar al campus** | `docker compose run --rm -it moodle-quiz submit --config /app/config.json` | `python moodle_quiz.py submit --config config.json` |

Antes de ejecutarlos necesitas `config.json` con `attempt`, `cmid`, `answers` y sesión (`cookie` o `MOODLE_QUIZ_COOKIE`). La primera vez: `docker compose build` y, si usarás IA, `docker compose up -d ollama` más `docker compose exec ollama ollama pull …` (ver arriba). En el paso 3, si `confirm_submit` es `true`, el script pregunta en consola; por eso Docker usa `-it` en `submit`. Con `"confirm_submit": false` puedes quitar `-it`.

## Requisitos

- **Docker** con Docker Compose (flujo principal de este README)
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

### Ollama en tu Mac (solo si no usas el contenedor `ollama`)

Si ya usas **Docker** con el servicio `ollama` del `docker-compose.yml`, **no instales** Ollama con Homebrew ni a mano: el flujo principal está en la sección **Solo Docker (+ Ollama en contenedor)** al inicio de este documento.

Para desarrollo sin Docker: [ollama.com](https://ollama.com/download) o `brew install ollama`, luego `ollama pull llama3.2` y en `config.json` (o variable) `base_url` apuntando a `http://127.0.0.1:11434`.

**Genera las respuestas** (misma `cookie` / intento que para `fetch`; no hace falta tener `answers` rellenado aún):

- **Docker (recomendado, Ollama ya en Compose):**

  ```bash
  docker compose run --rm -it moodle-quiz ollama-answers --config /app/config.json --answers-out /app/out/answers_ollama.json
  ```

- **Solo en tu máquina (Python + Ollama local):**

  ```bash
  python moodle_quiz.py ollama-answers --config config.json --answers-out answers_ollama.json
  ```

El comando imprime un JSON y opcionalmente lo guarda. Copia ese bloque dentro de `config.json` → `"answers"`, revisa los índices y luego usa `submit` como siempre.

Parámetros opcionales: `--ollama-url`, `--model`. En Docker la URL por defecto la fija `OLLAMA_BASE_URL` en `docker-compose.yml`. También puedes poner en `config.json` un objeto `"ollama": { "base_url": "...", "model": "..." }`.

**Docker con Ollama solo en el Mac (sin servicio `ollama` en Compose):** `OLLAMA_BASE_URL=http://host.docker.internal:11434` o `--ollama-url http://host.docker.internal:11434`.

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
| `ollama` | (Opcional) Para `ollama-answers`: `{"base_url": "http://127.0.0.1:11434", "model": "llama3.2"}`. En Docker suele bastar la variable de entorno `OLLAMA_BASE_URL` del `docker-compose.yml`. |

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
| `ollama-answers` | Descarga el intento y pide a **Ollama** (en Docker o en el host) un índice por pregunta; imprime JSON para `"answers"` |
| `run` | Hace `fetch` (guarda `quiz_snapshot.json`) y luego `submit` en un solo paso |

Ejemplos extra (host):

```bash
python moodle_quiz.py fetch -c config.json --snapshot ./backup.json
python moodle_quiz.py run --dry-run
python moodle_quiz.py run -c config.json
```

Equivalentes **Docker** (`./out` montado en `/app/out`):

```bash
docker compose run --rm moodle-quiz fetch --config /app/config.json --snapshot /app/out/backup.json
docker compose run --rm -it moodle-quiz run --dry-run
docker compose run --rm -it moodle-quiz run --config /app/config.json
```

## Flujo de trabajo recomendado

1. **Configura** `attempt`, `cmid` y sesión (`cookie` o `MOODLE_QUIZ_COOKIE`).
2. Ejecuta **`fetch`** y revisa en consola que el número de preguntas y los textos coinciden con lo que ves en el navegador.
3. Completa **`answers`** con los índices correctos (comprueba contra la lista `[0] a.`, `[1] b.`, etc.).
4. Ejecuta **`submit --dry-run`** y confirma que el resumen “Payload de respuestas” es el deseado.
5. Ejecuta **`submit`** (o **`run`**). Si `confirm_submit` es `true`, escribe `s` cuando pregunte.

Tras un envío correcto, el script suele indicar redirección a `summary.php` o `review.php`.

## Ejemplo paso a paso completo

Recorre estos pasos **en orden** la primera vez. El camino por defecto aquí es **Docker + Ollama en contenedor**; las variantes con Python en el PC son opcionales.

### 1. Preparar el proyecto (una vez por máquina)

**Con Docker (recomendado):**

```bash
cd script_de_evaluacion_de_temas
docker compose build
# Orden obligatorio: primero el servicio en marcha, luego exec (si no: «service ollama is not running»)
docker compose up -d ollama
docker compose exec ollama ollama pull llama3.2
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

En la raíz del repo (puedes partir de un JSON vacío de respuestas y rellenar después):

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

- Si prefieres no guardar la cookie en disco: deja `"cookie": ""` y en terminal `export MOODLE_QUIZ_COOKIE='...'` antes de cada comando.

### 4. Comprobar que el intento se lee bien

**Docker:**

```bash
docker compose run --rm moodle-quiz fetch --config /app/config.json
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py fetch --config config.json
```

Debes ver el mismo número de preguntas que en el navegador y textos coherentes.

### 5. Obtener `answers` (manual o con Ollama)

**Opción A — Manual:** edita `config.json` y rellena `"answers"` con índices `0`…`3` según la lista `[0] a.`, `[1] b.`, … del `fetch`.

**Opción B — Ollama en Docker (servicio `ollama` del `docker-compose.yml`):** asegúrate de tener `docker compose up -d ollama` y el modelo descargado (`docker compose exec ollama ollama pull llama3.2`). Luego:

```bash
docker compose run --rm -it moodle-quiz ollama-answers --config /app/config.json --answers-out /app/out/answers_ollama.json
```

El contenedor ya usa `OLLAMA_BASE_URL=http://ollama:11434`. Copia el JSON de `./out/answers_ollama.json` al campo `"answers"` de `config.json` y **revísalo**.

**Opción C — Ollama instalado en el Mac** (sin servicio `ollama` en Compose): deja Ollama escuchando en el host y ejecuta el cliente Docker con:

```bash
docker compose run --rm -it -e OLLAMA_BASE_URL=http://host.docker.internal:11434 moodle-quiz ollama-answers --config /app/config.json --answers-out /app/out/answers_ollama.json
```

**Opción D — Todo en el PC sin Docker** (Python + Ollama local):

```bash
ollama pull llama3.2   # u ollama serve / brew services según tu instalación
python moodle_quiz.py ollama-answers --config config.json --answers-out answers_ollama.json
```

### 6. Simular el envío (sin entregar)

**Docker:**

```bash
docker compose run --rm -it moodle-quiz submit --config /app/config.json --dry-run
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py submit --config config.json --dry-run
```

Comprueba el bloque “Payload de respuestas”.

### 7. Enviar al campus

**Docker:**

```bash
docker compose run --rm -it moodle-quiz submit --config /app/config.json
```

**Python en el PC (opcional):**

```bash
python moodle_quiz.py submit --config config.json
```

Si `confirm_submit` es `true`, escribe `s` cuando pregunte. Éxito habitual: **HTTP 200** y URL final con `summary.php` y luego `review.php` (el script envía también “Enviar todo y terminar” si aplica).

### 8. Hacer **otro** test después

Actualiza en `config.json` el **`attempt`** (y **`cmid`** si cambias de cuestionario). Renueva **`cookie`** / `MOODLE_QUIZ_COOKIE` si la sesión caducó. Repite desde el paso **4** (y **5** si usas Ollama de nuevo).

## Uso con Docker (detalles)

El flujo principal está al inicio de este documento (**Solo Docker (+ Ollama en contenedor)**) y en la tabla de **Los tres comandos principales**. Aquí, notas extra:

- `docker-compose.yml` monta `./config.json` en `/app/config.json` (solo lectura) y `./out` en `/app/out` para `answers_ollama.json` y snapshots. El `Dockerfile` usa por defecto `fetch` con ese archivo.
- Para **confirmación interactiva** en `submit`, usa **`-it`**. Si usas `confirm_submit: false`, no hace falta.
- Snapshot en el host:  
  `docker compose run --rm moodle-quiz fetch --config /app/config.json --snapshot /app/out/quiz_snapshot.json`
- Cookie sin guardarla en `config.json`:  
  `MOODLE_QUIZ_COOKIE='…' docker compose run --rm -e MOODLE_QUIZ_COOKIE moodle-quiz fetch --config /app/config.json`

## Solución de problemas

| Síntoma | Qué revisar |
|---------|-------------|
| `No se pudo parsear "cookie"` / texto `PEGA_AQUI...` | Sustituye `cookie` por la cadena real del header `cookie:` o usa `MOODLE_QUIZ_COOKIE`. |
| `HTTP 404` en `POST` a `processattempt.php` | Asegúrate de tener la última versión del script (copia todos los campos del formulario, no solo `input[type=hidden]`). Comprueba que el intento siga abierto en el navegador. Si persiste, mira el recorte del cuerpo que imprime el script (p. ej. Akamai). |
| Redirige al login | Cookie incompleta o expirada. |
| `submit` no avanza en Docker | Añade `-it` o pon `"confirm_submit": false`. |
| Faltan preguntas en `answers` | Debe existir una clave por cada número de pregunta mostrado en `fetch`. |
| `service "ollama" is not running` al hacer `docker compose exec ollama …` | **`exec` exige que el contenedor ya esté en marcha.** Primero: `docker compose up -d ollama`. Luego: `docker compose exec ollama ollama pull …`. Verifica con `docker compose ps` que el servicio `ollama` esté **Up**. |

## Aviso de uso responsable

Este proyecto automatiza peticiones HTTP equivalentes a usar el navegador. Úsalo solo donde la normativa del curso y del campus lo permitan. El envío automático de evaluaciones puede infringir reglas académicas; la responsabilidad es tuya.
