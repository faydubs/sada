from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str

    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"

    # رمز إنشاء حساب مسؤول من شاشة التسجيل — يمنع أي شخص من جعل نفسه مسؤولاً.
    # غيّره عبر ADMIN_SIGNUP_CODE في .env. اجعله فارغاً "" لتعطيل تسجيل المسؤول كلياً.
    ADMIN_SIGNUP_CODE: str = "tamr-admin-2025"

    ALLAM_API_URL: str | None = None
    ALLAM_API_KEY: str | None = None
    ALLAM_MODEL: str = "allam"

    # ── Gemini — اختياري: إذا غير موجود يُستخدم extractor.py تلقائياً
    GEMINI_API_KEY: str | None = None

    WHISPER_MODEL_SIZE: str = "medium"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_INITIAL_PROMPT: str | None = None

    # ── CORS: قائمة مصادر مسموحة، مفصولة بفاصلة. لا تستخدم "*" في الإنتاج.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """حوّل CORS_ORIGINS من نص مفصول بفاصلة إلى قائمة جاهزة لـ CORSMiddleware."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
