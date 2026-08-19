from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAMPUSGPT_", env_file=".env")

    data_dir: Path = Path("./data")
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 6
    confidence_threshold: float = 0.35

    # Required at first run; no defaults so accidental empty passwords fail loudly.
    admin_user: str = ""
    admin_pass: str = ""

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "campusgpt.db"

    @property
    def secret_key(self) -> str:
        # Stable per-install secret; can be overridden via env in production.
        return self.admin_user + "_" + "campusgpt_session_secret"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
