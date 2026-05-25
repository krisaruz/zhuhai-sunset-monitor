from pydantic import BaseModel


class ShootingLocationResponse(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    facing_azimuth_min: float
    facing_azimuth_max: float
    description: str | None
    best_seasons: list[str]
    tags: list[str]
    map_url: str | None

    model_config = {"from_attributes": True}
