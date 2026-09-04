from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = True
    
    # Official NWIC / CWC API configuration
    CWC_API_URL: str = "https://nwdp.nwic.gov.in/api/3/action/datastore_search"
    CWC_API_KEY: str = ""
    CWC_RESOURCE_ID: str = "cwc_hourly_water_level"
    
    # HydroSwift / CWC FFS endpoints
    CWC_FFS_API: str = "https://ffs.india-water.gov.in/iam/api/new-entry-data/specification/sorted"
    CWC_LAYER_STATION_BASE: str = "https://ffs.india-water.gov.in/iam/api/layer-station"
    INDIA_WRIS_BASE: str = "https://indiawris.gov.in/api"
    
    # Weather and upstream APIs
    OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_ELEVATION_URL: str = "https://api.open-meteo.com/v1/elevation"
    OPEN_METEO_FLOOD_URL: str = "https://flood-api.open-meteo.com/v1/flood"
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
    
    # CORS configuration
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]


settings = Settings()
