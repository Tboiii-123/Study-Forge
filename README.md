# StudyForge: AI Personal Notes + Study Packs

Capture notes (text or voice) in a self-chat style, then turn them into **summaries, flashcards and exam-style questions** with a model adapted using **Adaption** (Adaptive Data + AutoScientist).

Built for the **Build54 × Adaption** hackathon.

**Django 5 · DRF (function-based views only) · PostgreSQL · Redis · Celery · S3/MinIO · Adaption · Docker · GitHub Actions**

```
Client ──► Django/DRF API ──► PostgreSQL        (notes, study packs, FTS index)
                │  └────────► S3 / MinIO        (audio)
                └─ enqueue ─► Redis ─► Celery workers ─┬─► STT provider        (voice → text)
                                                       ├─► LLM provider        (naming, summaries)
                                                       └─► Adaption model      (study packs)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design decisions.

---

## What problem does it solve?

| Student problem | StudyForge feature |
|---|---|
| Notes pile up as "Untitled 37" | AI auto-naming + full-text search |
| Hard to write notes while the lecturer talks fast | Voice → text capture |
| Long notes are slow to revise | AI summaries |
| Passive reading doesn't stick | Flashcards for active recall |
| Students don't know how they'll be tested | Exam-style practice questions |
| Whole-semester notes are too long for one model call | Automatic chunking |
| Sharing with a study group is awkward | Public share links |
| Generic AI doesn't match the exam style | Model adapted on task-specific data |

---

## How Adaption is used

Adaption powers the **study-pack generation** only. Voice → text, search and sharing do not use it.

```
Idea → raw data → Adaptive Data → adapted dataset → AutoScientist → adapted model → StudyForge
```

1. **Raw data:** note chunks (100-300 words) paired with a summary, flashcards and practice questions in a fixed format.
2. **Adaptive Data:** imports and shapes the dataset (tone, length, grounding) and reports quality signals. Weak examples are removed.
3. **AutoScientist:** trains a small model (under 10B parameters) on the adapted dataset and evaluates it.
4. **StudyForge:** the study-pack Celery task calls the adapted model.
5. **Comparison:** the same held-out notes are run through a generic LLM and the adapted model.

### Long notes

Long notes are split into chunks (by heading, then by paragraph, about 200 words with a small overlap). Each chunk is processed separately, then results are merged, grouped by section, and de-duplicated.

---

## Quick start (Docker)

```bash
cp .env.example .env
make up                       # api :8000, worker, beat, postgres, redis, minio
make superuser                # optional, for /admin/
open http://localhost:8000/api/docs/   # Swagger UI
```

Runs fully offline by default using **fake AI providers**.

### Using real providers

```
# Speech-to-text and LLM (naming, summaries)
AI_STT_PROVIDER=apps.ai.providers.openai_provider.OpenAISTTProvider
AI_LLM_PROVIDER=apps.ai.providers.openai_provider.OpenAILLMProvider
OPENAI_API_KEY=sk-...

# Adaption (study packs)
ADAPTION_API_KEY=...
ADAPTION_MODEL_ID=<your-adapted-model-id>
```

> Check the [Adaption docs](https://docs.adaptionlabs.ai/) for how to access your adapted model, and adjust the `ADAPTION_*` settings to match.

## Local (no Docker)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env          # point DATABASE_URL / REDIS_URL at local services
python manage.py migrate && python manage.py runserver
celery -A config worker -l info -Q default,ai      # second terminal
celery -A config beat -l info                      # third terminal (optional)
```

## Tests & quality

```bash
pytest --cov=apps             # needs Postgres (uses DATABASE_URL); Celery runs eagerly
ruff check . && ruff format --check .
```

---

## API (all under `/api/v1`)

### Auth

| Method | Path | Purpose |
|---|---|---|
| POST | `auth/register/` `auth/login/` `auth/refresh/` `auth/logout/` | JWT auth (refresh rotation + blacklist) |
| GET/PATCH | `auth/me/` | Profile |
| POST | `auth/password-reset/` · `auth/password-reset/confirm/` | Reset flow |

### Notes

| Method | Path | Purpose |
|---|---|---|
| POST | `capture/` | **Capture first**: text or audio; creates + AI-names a container if none given |
| GET/POST | `containers/` | List (cursor-paginated) / create |
| GET/PATCH/DELETE | `containers/{id}/` | Rename, archive, delete |
| GET/POST | `containers/{id}/entries/` | Timeline / add text or audio (**202 Accepted**, poll `status`) |
| GET/PATCH/DELETE | `entries/{id}/` | Edit text/transcript (re-runs AI), delete |
| POST | `entries/{id}/retry/` | Retry a FAILED entry |

### Study packs (new)

| Method | Path | Purpose |
|---|---|---|
| POST | `entries/{id}/study-pack/` | Generate a study pack (summary, flashcards, exam questions). **202 Accepted** |
| GET | `entries/{id}/study-pack/status/` | Poll status and fetch the generated material |

### Summaries, sharing, search, health

| Method | Path | Purpose |
|---|---|---|
| POST | `containers/{id}/summary/` | Async AI summary: `today/yesterday/week/month/all/custom` |
| POST/DELETE | `containers/{id}/share/` | Publish / unpublish |
| GET | `public/{public_id}/` | Anonymous JSON of a public container |
| GET | `/share/{public_id}/` | Anonymous server-rendered web page |
| GET | `search/?q=&container=` | Full-text search with highlighted snippets |
| GET | `/health/live/` `/health/ready/` | Probes |

### Lifecycles

```
Entry:      pending → transcribing → analyzing → completed | failed
StudyPack:  pending → generating → completed | failed
```

---

## Example workflow

**1. Capture a note**

```bash
curl -X POST http://localhost:8000/api/v1/capture/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Photosynthesis is the process by which plants convert light energy into chemical energy...",
    "container_name": "Biology 101"
  }'
```

**2. Generate a study pack**

```bash
curl -X POST http://localhost:8000/api/v1/entries/5/study-pack/ \
  -H "Authorization: Bearer TOKEN"
# 202 Accepted
# { "id": 1, "entry": 5, "status": "generating", "summary": null, "flashcards": [], "exam_questions": [] }
```

**3. Poll for the result**

```bash
curl http://localhost:8000/api/v1/entries/5/study-pack/status/ \
  -H "Authorization: Bearer TOKEN"
# 200 OK
# {
#   "id": 1, "entry": 5, "status": "completed",
#   "summary": "Photosynthesis converts light energy to chemical energy in chloroplasts...",
#   "flashcards": [{"q": "What is photosynthesis?", "a": "..."}],
#   "exam_questions": [{"question": "...", "options": ["..."], "answer": "B"}]
# }
```

---

## Results: generic vs adapted model

Fill this in after your evaluation. Report only what your evidence supports.

| Metric (on held-out notes) | Generic LLM | Adapted model |
|---|---|---|
| Follows the required output format | _TBD_ | _TBD_ |
| Stays faithful to the notes | _TBD_ | _TBD_ |
| Exam-style question quality (manual rating) | _TBD_ | _TBD_ |

Dataset size: _TBD_ examples · Held-out test set: _TBD_ examples · Base model size: _TBD_

---

## Deploy

CI (`.github/workflows/ci.yml`) runs lint → migrations check → tests (Postgres service, ≥80% coverage) → builds and pushes
the `runtime` image to GHCR on `main`. `deploy.yml` then rolls it out over SSH using `docker-compose.prod.yml`
(swap for ECS/Fly/K8s as needed). Required secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`.

## Layout

```
config/            settings (base/dev/prod/test), urls, celery app
apps/common/       base models, cursor pagination, throttles, error envelope, health
apps/users/        email-login User, JWT auth views
apps/containers/   Container & Entry models, services (transactions), views
apps/study_packs/  StudyPack model, chunking, Adaption integration, Celery tasks
apps/ai/           provider interfaces (fake/OpenAI), Celery pipeline tasks
apps/sharing/      publish/unpublish, public selectors, HTML template
apps/search/       Postgres full-text search
tests/             pytest suite
docs/              architecture and deployment notes
```

## Links

- Adaption: https://adaptionlabs.ai
- Docs: https://docs.adaptionlabs.ai/
- Community: https://discord.gg/adaption

## Contributing

Run `ruff check . && ruff format .`, add tests for new features, and make sure `pytest --cov=apps` passes.

## License

MIT