import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

VALID_SANDBOX_RUNTIMES = ("runc", "runsc")
PRODUCTION_SANDBOX_RUNTIME = "runsc"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"


class ConfigurationError(Exception):
    pass


def env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    value = env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ConfigurationError(f"{name} must be an integer.")


def env_float(name: str, default: float) -> float:
    value = env_str(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ConfigurationError(f"{name} must be a number.")


def env_bool(name: str, default: bool) -> bool:
    value = env_str(name)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ConfigurationError(f"{name} must be true or false.")


def env_list(name: str) -> list[str]:
    value = env_str(name)
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_environment() -> str:
    return env_str("ENVIRONMENT", "development")


def validate_sandbox_runtime(environment: str | None, runtime: str | None) -> str:
    value = (runtime or "").strip()
    if environment == "production":
        if value != PRODUCTION_SANDBOX_RUNTIME:
            raise ConfigurationError(
                "SANDBOX_DOCKER_RUNTIME must be set to runsc when ENVIRONMENT is production."
            )
        return value
    if value not in VALID_SANDBOX_RUNTIMES:
        raise ConfigurationError(
            "SANDBOX_DOCKER_RUNTIME must be set explicitly to runc or runsc."
        )
    return value


def get_sandbox_runtime() -> str:
    return validate_sandbox_runtime(get_environment(), os.getenv("SANDBOX_DOCKER_RUNTIME"))


def get_sandbox_output_cap_bytes() -> int:
    return env_int("SANDBOX_OUTPUT_CAP_BYTES", 20 * 1024 * 1024)


@dataclass(frozen=True)
class Settings:
    environment: str
    supabase_url: str | None
    supabase_service_role_key: str | None
    anthropic_api_key: str | None
    anthropic_model: str
    cors_origins: list[str]
    allow_upload: bool
    trust_proxy: bool
    ip_hash_salt: str | None
    rate_limit_runs: int
    rate_limit_window_seconds: int
    daily_analysis_cap: int
    max_date_range_years: int
    max_model_file_bytes: int
    max_features: int
    max_csv_bytes: int
    max_csv_rows: int
    shap_sample_size: int
    shap_min_rows_per_regime: int
    shap_low_sample_threshold: int
    shap_max_trade_rows: int
    shap_background_rows: int
    shap_kernel_nsamples: int
    shap_kernel_background_size: int
    job_timeout_seconds: float
    max_concurrent_jobs: int
    continuous_signal_dead_zone: float
    preflight_rows: int
    report_max_tokens: int


def get_settings() -> Settings:
    return Settings(
        environment=get_environment(),
        supabase_url=env_str("SUPABASE_URL"),
        supabase_service_role_key=env_str("SUPABASE_SERVICE_ROLE_KEY"),
        anthropic_api_key=env_str("ANTHROPIC_API_KEY"),
        anthropic_model=env_str("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        cors_origins=env_list("CORS_ORIGINS"),
        allow_upload=env_bool("ALLOW_UPLOAD", True),
        trust_proxy=env_bool("TRUST_PROXY", False),
        ip_hash_salt=env_str("IP_HASH_SALT"),
        rate_limit_runs=env_int("RATE_LIMIT_RUNS", 5),
        rate_limit_window_seconds=env_int("RATE_LIMIT_WINDOW_SECONDS", 3600),
        daily_analysis_cap=env_int("DAILY_ANALYSIS_CAP", 200),
        max_date_range_years=env_int("MAX_DATE_RANGE_YEARS", 10),
        max_model_file_bytes=env_int("MAX_MODEL_FILE_BYTES", 10 * 1024 * 1024),
        max_features=env_int("MAX_FEATURES", 30),
        max_csv_bytes=env_int("MAX_CSV_BYTES", 5 * 1024 * 1024),
        max_csv_rows=env_int("MAX_CSV_ROWS", 20000),
        shap_sample_size=env_int("SHAP_SAMPLE_SIZE", 600),
        shap_min_rows_per_regime=env_int("SHAP_MIN_ROWS_PER_REGIME", 30),
        shap_low_sample_threshold=env_int("SHAP_LOW_SAMPLE_THRESHOLD", 100),
        shap_max_trade_rows=env_int("SHAP_MAX_TRADE_ROWS", 200),
        shap_background_rows=env_int("SHAP_BACKGROUND_ROWS", 100),
        shap_kernel_nsamples=env_int("SHAP_KERNEL_NSAMPLES", 200),
        shap_kernel_background_size=env_int("SHAP_KERNEL_BACKGROUND_SIZE", 10),
        job_timeout_seconds=env_float("JOB_TIMEOUT_SECONDS", 300.0),
        max_concurrent_jobs=env_int("MAX_CONCURRENT_JOBS", 2),
        continuous_signal_dead_zone=env_float("CONTINUOUS_SIGNAL_DEAD_ZONE", 0.0),
        preflight_rows=env_int("PREFLIGHT_ROWS", 5),
        report_max_tokens=env_int("REPORT_MAX_TOKENS", 16000),
    )
