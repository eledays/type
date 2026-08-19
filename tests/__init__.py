"""Application tests."""
import os


os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-test-suite")
