import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.models.location import ShootingLocation
from src.services.astronomer import get_season


@dataclass(frozen=True)
class LocationRecommendation:
    name: str
    lat: float
    lon: float
    facing_azimuth: float
    description: str
    tags: list[str]
    map_url: str | None
    score: float
    reason: str
    suggested_arrival: str


def _azimuth_alignment_score(sunset_azimuth: float, az_min: float, az_max: float) -> float:
    """Score 1.0 if sunset azimuth is within range, decay linearly outside."""
    if az_min <= sunset_azimuth <= az_max:
        return 1.0
    dist = min(abs(sunset_azimuth - az_min), abs(sunset_azimuth - az_max))
    return max(0.0, 1.0 - dist / 30.0)


def _season_match_score(current_season: str, best_seasons: list[str]) -> float:
    if "all" in best_seasons or current_season in best_seasons:
        return 1.0
    # Adjacent seasons get partial score
    adjacent = {
        "spring": ["summer", "winter"],
        "summer": ["spring", "autumn"],
        "autumn": ["summer", "winter"],
        "winter": ["autumn", "spring"],
    }
    if current_season in adjacent.get(current_season, []):
        return 0.5
    return 0.2


def recommend_locations(
    sunset_azimuth: float,
    sunset_time: datetime,
    all_locations: list[ShootingLocation],
    top_n: int = 3,
) -> list[LocationRecommendation]:
    """Score and rank shooting locations based on sunset conditions."""
    current_season = get_season(sunset_time.date())

    scored: list[tuple[float, ShootingLocation, str]] = []
    for loc in all_locations:
        if not loc.active:
            continue

        az_score = _azimuth_alignment_score(
            sunset_azimuth, loc.facing_azimuth_min, loc.facing_azimuth_max
        )

        best_seasons = json.loads(loc.best_seasons) if loc.best_seasons else ["all"]
        season_score = _season_match_score(current_season, best_seasons)

        total_score = az_score * 0.6 + season_score * 0.4

        facing_center = (loc.facing_azimuth_min + loc.facing_azimuth_max) / 2
        reason = f"日落方位角{sunset_azimuth:.0f}°，{loc.name}朝向{facing_center:.0f}°"
        if az_score > 0.8:
            reason += "，完美对齐"
        elif az_score > 0.5:
            reason += "，角度接近"

        scored.append((total_score, loc, reason))

    scored.sort(key=lambda x: x[0], reverse=True)

    arrival = sunset_time - timedelta(minutes=30)
    arrival_str = arrival.strftime("%H:%M")

    results: list[LocationRecommendation] = []
    for score, loc, reason in scored[:top_n]:
        tags = json.loads(loc.tags) if loc.tags else []
        results.append(
            LocationRecommendation(
                name=loc.name,
                lat=loc.lat,
                lon=loc.lon,
                facing_azimuth=(loc.facing_azimuth_min + loc.facing_azimuth_max) / 2,
                description=loc.description or "",
                tags=tags,
                map_url=loc.map_url,
                score=round(score, 3),
                reason=reason,
                suggested_arrival=arrival_str,
            )
        )

    return results
