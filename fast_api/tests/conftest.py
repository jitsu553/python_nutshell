import os

os.environ.setdefault("SECRET_KEY", "test-only-secret")  # tests never use the real key