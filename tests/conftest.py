"""Environment required before pytest imports application modules."""

import os


os.environ.setdefault("LEGAL_OPERATOR_NAME", "Test operator")
os.environ.setdefault("LEGAL_OPERATOR_ADDRESS", "Test address")
os.environ.setdefault("LEGAL_CONTACT_EMAIL", "privacy@example.test")
