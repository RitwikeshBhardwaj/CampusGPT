# CampusGPT

Local RAG assistant for university documents.

## Setup
1. Install Ollama: https://ollama.com
2. Pull the model: `ollama pull llama3.1:8b`
3. Start the server: `ollama serve` (in another terminal)
4. Install Python deps: `pip install -e ".[dev]"`
5. Seed an admin: `CAMPUSGPT_ADMIN_USER=admin CAMPUSGPT_ADMIN_PASS=changeme python -m campusgpt.bootstrap`
6. Run the backend: `uvicorn app.main:app --reload`
