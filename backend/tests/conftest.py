import os

# Force tests onto an isolated local SQLite database, regardless of any
# DATABASE_URL that may exist in the parent shell or deployment environment.
os.environ["JWT_SECRET"] = "test-secret-for-security-tests-only-not-production"
os.environ["DATABASE_URL"] = "sqlite:///./test_security.db"
os.environ["RATE_LIMIT_ENABLED"] = "0"
os.environ["EMAIL_ENABLED"] = "0"
os.environ["RECOVERY_CODE_PEPPER"] = "test-recovery-pepper"
