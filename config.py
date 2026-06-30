from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "vedic-astro-backend"
    app_env: str = "development"
    secret_key: str = Field(..., min_length=32)
    debug: bool = False
    mongodb_uri: str
    mongodb_db_name: str = "vedic_astro"
    openai_api_key: str
    llm_api_key: str = ""
    llm_base_url: str = ""
    # Embeddings use a separate key/URL so they can use OpenAI even when LLM is Groq
    embedding_api_key: str = ""       # defaults to openai_api_key if empty
    embedding_base_url: str = ""      # leave empty for standard OpenAI endpoint
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    openai_synthesis_model: str = "gpt-4o"
    openai_classifier_model: str = "gpt-4o-mini"
    openai_reasoning_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    jina_api_key: str = ""
    prokerala_client_id: str
    prokerala_client_secret: str
    prokerala_token_url: str = "https://api.prokerala.com/token"
    prokerala_base_url: str = "https://api.prokerala.com/v2/astrology"
    max_retrieval_chunks: int = 8
    max_conversation_turns: int = 4
    # Phase 3 depth: review the draft reading against the deterministic blocks and refine out
    # any generic/ungrounded claim before the user sees it. Costs one extra LLM call per
    # message (more when a refine is actually needed); accuracy is the priority here.
    enable_verification_pass: bool = True
    max_session_summaries: int = 5
    # Raised from 4000 so the deterministic depth (graded yogas, planetary states, bhava-lord
    # placements, nakshatra layer) survives trimming alongside the chart + bundles. The live
    # models have 32k+ context, so this is well within budget.
    prompt_token_budget: int = 6500
    # Comma-separated allowed CORS origins. "*" is permitted only without credentials
    # (browsers reject wildcard-with-credentials); pin real origins in production.
    cors_allow_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()] or ["*"]

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "develop", "dev"}:
                return True
        return value


settings = Settings()
