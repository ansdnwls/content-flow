from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "change-me-in-production"

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    # Redis (Week 2)
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_test_env(self) -> bool:
        return self.app_env == "test"


settings = Settings()
