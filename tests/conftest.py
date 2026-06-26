import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("COHERE_API_KEY", "test-cohere-key")
os.environ.setdefault("PROKERALA_CLIENT_ID", "test-client")
os.environ.setdefault("PROKERALA_CLIENT_SECRET", "test-secret")
