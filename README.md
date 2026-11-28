# MedResolve

**A patient-context-aware medical information assistant (research prototype).**

MedResolve answers a patient's health question using **their own medical history**: conditions, current and past medicines, allergies, earlier symptoms, visits and lab results. Every statement about the patient must cite the record it comes from. The app shows which records and which medical references shaped each answer.

> ⚠️ **Academic research prototype.** It is **not** a diagnostic or prescribing system, and it is **not** clinically validated. The demo patients are synthetic (Synthea). Never rely on it for real medical decisions.

**Team:** Kaushik Kumar Reddy S, Abhiram Boyidi. **Guide:** Dr. B. Jothi (SRM).

| Document | Read it for |
|---|---|
| `README.md` (this file) | Installing, configuring, starting and stopping the app |
| [`TECHNICAL_DOCUMENTATION.md`](TECHNICAL_DOCUMENTATION.md) | How the system was built: technologies, models, architecture, workflows, evaluation |
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | Finding your way around the code, making changes, debugging, testing |

---

## 1. What you need

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 (3.10–3.12 work) | The app is developed and tested on 3.11.0 |
| Node.js + npm | 20 or newer | For the React web app |
| [Ollama](https://ollama.com) | Latest | Runs the local answer-writing model. Nothing is sent to the internet. |
| ffmpeg | Any recent build | Only needed for **speech-to-text** (the microphone button) |
| RAM / disk | 16 GB RAM recommended, ~10 GB free disk | BGE-M3 embeddings (~2.3 GB), llama3.2:3b (~2 GB), Whisper base (~150 MB) |
| GPU | **Not needed** | The whole app runs on CPU. A GPU is only needed to *train* the Mistral-7B router. |

All commands below are for **Windows PowerShell**, run from the project folder (`D:\MedResolve`). On Linux or macOS, the same commands work with `/` instead of `\`.

---

## 2. Install (one time)

### 2.1 Python packages

Optionally, create a virtual environment first:

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install the packages:

```powershell
python -m pip install -r requirements.txt
```

### 2.2 Web app packages

```powershell
npm --prefix frontend install
```

### 2.3 Local language model (Ollama)

Install Ollama from https://ollama.com, then download the default model:

```powershell
ollama pull llama3.2:3b
```

### 2.4 ffmpeg (only for speech-to-text)

```powershell
winget install --id Gyan.FFmpeg -e
```

The backend finds ffmpeg on `PATH`, in the WinGet package folder, or at the path in `FFMPEG_PATH`.

### 2.5 Data and indexes

The patient database, datasets and models are **not** in Git, because they are large or private (see `.gitignore`). On a fresh copy, build them in this order:

1. **Download the public datasets and tools** (MedlinePlus, SearchTome, the Synthea sample, plus the Synthea jar and a JDK into `tools/`):

   ```powershell
   python scripts/download_datasets.py
   ```

2. **Generate the synthetic patients.** This uses the downloaded JDK and needs Git Bash or WSL to run the shell script:

   ```powershell
   bash scripts/generate_synthea.sh
   ```

3. **Load the patients into the database** (`data/medresolve.db`):

   ```powershell
   python -m backend.fhir_ingestion.synthea_ingest --input data/datasets/synthea/raw/generated_p600_seed20261101/fhir --tag generated_p600_seed20261101 --reset
   ```

4. **Build the medical reference corpus.** It powers the cited general-medicine passages:

   ```powershell
   python -m backend.rag.reference_corpus
   ```

5. **Optional: generate the router's training and evaluation questions:**

   ```powershell
   python -m backend.stair_retriever.training_data
   ```

**Models that download themselves:**

- **BGE-M3** embeddings download into `models/embeddings` on first use.
- **Whisper base** downloads into `models/whisper` the first time someone uses the microphone.

**The router adapter is optional.** The trained STAIR-Clinical router (`models/stair_clinical/adapters/current`) is not in Git. Without it, the app automatically uses the structural router (see `STAIR_BACKEND` below). To train one, see [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md#8-training-and-evaluation).

---

## 3. Configure

Every setting has a working default. To change one, set an environment variable before starting the backend, for example:

```powershell
$env:OLLAMA_MODEL = "llama3.2:3b"
```

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/medresolve.db` | Database. PostgreSQL also works: `postgresql+psycopg2://user:pass@host:5432/medresolve` |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama is running. Keep it local. |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model that writes the answers |
| `OLLAMA_TIMEOUT_S` | `180` | Seconds to wait for one answer |
| `USE_OLLAMA` | `1` | `0` turns off the LLM; answers then use a fixed template |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Dense retrieval model |
| `STAIR_BACKEND` | `auto` | Router choice. `auto` uses the LoRA adapter if one exists, otherwise `structural`. Other values: `lora`, `ollama`, `structural`. |
| `STAIR_ADAPTER_DIR` | `models/stair_clinical/adapters/current` | Where the trained router adapter is stored |
| `JWT_SECRET` | Generated into `data/.jwt_secret` | Key that signs login tokens. Set your own in any shared deployment. |
| `JWT_EXPIRE_MINUTES` | `720` | How long a login lasts (12 hours) |
| `MEDRESOLVE_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Web addresses allowed to call the API (comma-separated) |
| `MEDRESOLVE_WHISPER_MODEL` | `base` | Whisper size for speech-to-text (`tiny`, `base`, `small`, …) |
| `FFMPEG_PATH` | Auto-detected | Full path to `ffmpeg.exe`, if it can't be found automatically |
| `MEDRESOLVE_TODAY` | Real date | Pins "today" (`YYYY-MM-DD`) for repeatable evaluations |

---

## 4. Start the application

You need **three things running**: Ollama, the backend API and the web app. Use a separate terminal for each.

**1. Ollama.** It usually starts by itself as a background service after installation. Check it with:

```powershell
ollama list
```

If that fails, start it with:

```powershell
ollama serve
```

**2. Backend API** (FastAPI on port 8000):

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The first question after start-up takes longer, because it loads the embedding model and indexes. Wait for `Application startup complete`. You can check the API is up at http://127.0.0.1:8000/api/health.

**3. Web app** (Vite on port 5173):

```powershell
npm --prefix frontend run dev
```

Open **http://localhost:5173**. The web app forwards `/api` calls to port 8000.

**In the Claude desktop app**, `.claude/launch.json` defines the same servers as `medresolve-api` and `medresolve-web`.

### First use

- **Create an account**, then complete the short set-up: profile, conditions, medicines and allergies. A person with no medical history can finish set-up with nothing added and still gets general answers.
- **Or open a synthetic demo patient** from the sign-in page. Demo patients are read-only, and each browser session sees only its own questions.
- **Ask a question** on the Ask screen. You can type it or use the 🎤 microphone.
- **Choose an answer mode** above the question box:
  - **Use my memory** (default): the answer uses your health record.
  - **Normal**: a general answer; your record is not read.
  - **Compare both**: both answers side by side, with a short "What your memory changed" summary, so you can see exactly where your record made a difference (for example, a medicine removed because of an allergy).

  The choice is remembered in your browser.
- **Upload reports** (PDF or photo) on the Documents screen. Check the extracted values before they are saved.
- **Research → Test cases (40)** shows the 40 diagnostic vignettes with the AI's choices and reasoning.

---

## 5. Stop the application

- **Backend or web app:** press **Ctrl + C** in its terminal.
- **If a terminal was closed but the server is still running**, stop whatever holds the port:

  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Confirm:$false }
  ```

  ```powershell
  Get-NetTCPConnection -LocalPort 5173 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Confirm:$false }
  ```

- **Ollama:** quit it from the system tray, or:

  ```powershell
  Stop-Process -Name ollama -Confirm:$false
  ```

- **In the Claude desktop app**, stop `medresolve-api` and `medresolve-web` from the preview panel.

Stopping does not delete data. Accounts, records and uploads stay in `data/medresolve.db` and `data/uploads/`.

---

## 6. Check that everything works

Run the backend tests:

```powershell
python -m pytest
```

Type-check and build the frontend:

```powershell
npm --prefix frontend run build
```

You can also check component status (LLM, embedding model, router adapter, datasets) at http://127.0.0.1:8000/api/v2/system/status.

---

## 7. Common problems

| Problem | Fix |
|---|---|
| Answers say the AI model is unavailable | Ollama isn't running, or the model wasn't pulled. Run `ollama list` and `ollama pull llama3.2:3b`. |
| First answer is very slow | Normal: the embedding model and indexes load on first use. Later answers are faster. |
| No demo patients on the sign-in page | The database is empty. Run steps 2.5 (2) and (3). |
| Answers have no reference citations | The reference corpus wasn't built. Run `python -m backend.rag.reference_corpus` and restart the backend. |
| Microphone gives an ffmpeg error | Install ffmpeg (2.4), or set `FFMPEG_PATH`. |
| Web app shows network errors | The backend isn't on port 8000, or `MEDRESOLVE_CORS_ORIGINS` doesn't include the web app's address. |
| Backend code changes have no effect | Restart the backend. It runs without `--reload`. |
| `401 Unauthorized` after a while | The login expired (12 h by default). Sign in again. |
| `429 Too many attempts` at login | 5 failed logins lock the account for 15 minutes. |

More debugging help: [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md#7-debugging).

---

## 8. Data and privacy

- **Everything runs on your computer.** Questions, records, audio and documents are never sent to an external service.
- **Real patient data is never committed to Git.** The database, uploads and secret key are in `.gitignore`.
- **Restricted MIMIC data is never sent to external LLM APIs.**
- **Datasets:** Synthea (synthetic), the MIMIC-IV FHIR demo and the eICU-CRD demo (public demo releases), MedlinePlus, WHO fact sheets and FDA DailyMed labels. See `docs/dataset_documentation.md`.

## 9. Other apps in this repository

- **`doctor_assessment_app/`** is a separate app where doctors answer the 40 diagnostic vignettes. It shares no code or data with MedResolve; see its own `README.md`.
- **`docs/paper/`** holds the IEEE paper and its build script.
