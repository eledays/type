"""Application tests."""
import os


os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-test-suite-32chars")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/15")
