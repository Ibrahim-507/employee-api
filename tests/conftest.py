import os

# Fake values so tests never need a real .env or real secrets.
# Must be set BEFORE the app is imported.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
