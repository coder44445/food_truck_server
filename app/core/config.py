from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field(validate_default=False)
    SECRET_KEY: str = Field(validate_default=False)
    ALGORITHM: str = Field(validate_default=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(validate_default=False)
    
    
    # Redis Settings
    REDIS_HOST: str = Field(validate_default=False)
    REDIS_PORT: int = Field(validate_default=False)

    class Config:
        # Load environment variables from a .env file
        env_file = ".env"

        # Allow extra environment variables
        extra = "allow"

settings = Settings()
