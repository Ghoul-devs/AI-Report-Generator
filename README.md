# AI Research Report Generator

AI Research Report Generator is a web app for researching a topic and producing a source-backed report. Its FastAPI backend coordinates a six-stage agent pipeline, combining web search and uploaded documents with retrieval-augmented generation. The React frontend provides report setup, progress, sources, saved reports, and account management.

## Features

- Generate reports with planner, researcher, analyst, verifier, writer, and reviewer agents.
- Search the web and upload documents to use as research sources.
- View source references, report progress, and saved reports.
- Register and sign in, with feedback and password-reset email support.
- Run with mock AI responses for local development, or connect a Groq API key for generated responses.

## Requirements

- Python 3.10 or newer
- Node.js and npm
- A Groq API key for live AI generation (optional when using mock mode)
- SMTP credentials for feedback notifications and password-reset email (optional for local exploration)

## Setup

### Backend

From the repository root, create and activate a virtual environment, install dependencies, and configure environment variables:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

The example environment file contains SMTP settings. Fill them in to enable feedback notifications and password-reset emails. For live AI generation, add these settings to `backend/.env`:

```dotenv
USE_MOCK_AI=false
GROQ_API_KEY=your-groq-api-key
```

Mock mode is enabled by default when `USE_MOCK_AI` is unset. Keep API keys and SMTP credentials private; do not commit `.env`.

Start the API from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`; its interactive documentation is at `http://localhost:8000/docs`.

### Frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite (by default, `http://localhost:5173`).

## Development

Run the frontend lint and production build from `frontend`:

```powershell
npm run lint
npm run build
```

The backend initializes its SQLite database on startup. Local database files, uploaded files, generated reports, virtual environments, and frontend build output are excluded from Git.