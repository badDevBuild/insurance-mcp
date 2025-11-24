import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Project Root
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
    
    # Data Directories
    DATA_DIR = PROJECT_ROOT / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    DB_DIR = DATA_DIR / "db"
    VECTOR_STORE_DIR = DATA_DIR / "vector_store"
    ASSETS_DIR = PROJECT_ROOT / "assets"
    TABLE_EXPORT_DIR = ASSETS_DIR / "tables"

    # Database
    DB_PATH = DB_DIR / "metadata.sqlite"
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Crawler Settings
    USER_AGENT = "InsuranceMCP/1.0 (+https://github.com/yourusername/insurance-mcp)"
    DOWNLOAD_DELAY = 1.0  # Seconds
    MAX_RETRIES = 3
    
    # Rate Limiting (FR-008 & EC-003 Compliance)
    GLOBAL_QPS = float(os.getenv("CRAWLER_GLOBAL_QPS", "0.8"))  # < 1 QPS for compliance
    PER_DOMAIN_QPS = float(os.getenv("CRAWLER_PER_DOMAIN_QPS", "0.8"))
    CIRCUIT_BREAKER_ENABLED = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
    CIRCUIT_BREAKER_COOLDOWN = int(os.getenv("CIRCUIT_BREAKER_COOLDOWN", "300"))  # 5 minutes
    
    # Docling Settings
    DOCLING_MODEL_PATH = os.getenv("DOCLING_MODEL_PATH", None)  # Optional: Path to local model cache
    ENABLE_TABLE_SEPARATION = os.getenv("ENABLE_TABLE_SEPARATION", "true").lower() == "true"
    
    # MCP Settings
    MCP_SERVER_NAME = "insurance-mcp-core"

    @classmethod
    def ensure_dirs(cls):
        """Ensure all data directories exist."""
        cls.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        cls.TABLE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

config = Config()

