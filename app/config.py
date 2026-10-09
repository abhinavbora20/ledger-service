import os

from dotenv import load_dotenv

# Reads variables from a local .env file (ignored by Git) into the environment.
# Variables already set in the real environment win.
load_dotenv()

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


def get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    return secret
