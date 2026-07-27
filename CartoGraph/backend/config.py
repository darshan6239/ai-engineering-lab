"""
Central configuration. Loads settings from a .env file so credentials
never need to be hardcoded or committed to version control.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    groq_api_key: str

    @classmethod
    def load(cls) -> "Settings":
        missing = []
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        pwd = os.getenv("NEO4J_PASSWORD")
        api_key = os.getenv("GROQ_API_KEY")

        for name, val in [
            ("NEO4J_URI", uri),
            ("NEO4J_USERNAME", user),
            ("NEO4J_PASSWORD", pwd),
        ]:
            if not val:
                missing.append(name)

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in your Neo4j + Groq credentials."
            )

        return cls(
            neo4j_uri=uri,
            neo4j_username=user,
            neo4j_password=pwd,
            groq_api_key=api_key or "",
        )


settings = Settings.load()
