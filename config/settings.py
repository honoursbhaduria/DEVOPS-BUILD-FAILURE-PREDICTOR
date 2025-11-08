from pydantic import BaseSettings

class Settings(BaseSettings):
    JENKINS_URL: str
    JENKINS_USER: str
    JENKINS_TOKEN: str
    JENKINS_JOB_NAME: str

    DATABASE_URL: str
    REDIS_URL: str

    MODEL_PATH: str = "/app/model/predictor.pkl"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CHECK_INTERVAL_SECONDS: int = 60
    RISK_THRESHOLD: float = 0.7

    class Config:
        env_file = "config/.env"

settings = Settings()
