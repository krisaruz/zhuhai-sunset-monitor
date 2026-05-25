"""Seed predefined Zhuhai shooting locations into the database."""
import asyncio
import json

from src.models.database import async_session, init_db
from src.models.sunset import SunsetRecord  # noqa: F401 - ensure table creation
from src.models.location import ShootingLocation, NotificationLog  # noqa: F401

LOCATIONS = [
    {
        "name": "情侣路",
        "lat": 22.2475,
        "lon": 113.5720,
        "facing_azimuth_min": 230,
        "facing_azimuth_max": 270,
        "description": "珠海最著名的海滨步道，沿海岸线延伸，视野开阔无遮挡",
        "best_seasons": json.dumps(["autumn", "winter"]),
        "tags": json.dumps(["海边", "长廊", "日落步道"]),
        "map_url": "https://uri.amap.com/marker?position=113.5720,22.2475&name=情侣路",
    },
    {
        "name": "珠海渔女雕像",
        "lat": 22.2530,
        "lon": 113.5765,
        "facing_azimuth_min": 240,
        "facing_azimuth_max": 280,
        "description": "珠海地标，石雕渔女矗立海中，日落时可拍摄经典剪影",
        "best_seasons": json.dumps(["all"]),
        "tags": json.dumps(["地标", "剪影", "海边"]),
        "map_url": "https://uri.amap.com/marker?position=113.5765,22.2530&name=珠海渔女",
    },
    {
        "name": "日月贝歌剧院",
        "lat": 22.2380,
        "lon": 113.5650,
        "facing_azimuth_min": 250,
        "facing_azimuth_max": 290,
        "description": "珠海大剧院，贝壳造型独特建筑，日落前景极佳",
        "best_seasons": json.dumps(["all"]),
        "tags": json.dumps(["建筑", "剪影", "海边"]),
        "map_url": "https://uri.amap.com/marker?position=113.5650,22.2380&name=日月贝歌剧院",
    },
    {
        "name": "横琴大桥",
        "lat": 22.1850,
        "lon": 113.5350,
        "facing_azimuth_min": 240,
        "facing_azimuth_max": 270,
        "description": "可拍摄澳门城市天际线与日落的组合，现代都市感",
        "best_seasons": json.dumps(["all"]),
        "tags": json.dumps(["城市天际线", "澳门方向", "桥梁"]),
        "map_url": "https://uri.amap.com/marker?position=113.5350,22.1850&name=横琴大桥",
    },
    {
        "name": "唐家湾沙滩",
        "lat": 22.3600,
        "lon": 113.6100,
        "facing_azimuth_min": 250,
        "facing_azimuth_max": 290,
        "description": "珠海北部安静海滩，人少开阔，适合春夏拍摄",
        "best_seasons": json.dumps(["spring", "summer"]),
        "tags": json.dumps(["海边", "人少", "开阔"]),
        "map_url": "https://uri.amap.com/marker?position=113.6100,22.3600&name=唐家湾沙滩",
    },
    {
        "name": "野狸岛",
        "lat": 22.2370,
        "lon": 113.5630,
        "facing_azimuth_min": 250,
        "facing_azimuth_max": 280,
        "description": "日月贝旁的小岛，360度海景，可多角度拍摄",
        "best_seasons": json.dumps(["all"]),
        "tags": json.dumps(["360度海景", "日月贝旁", "小岛"]),
        "map_url": "https://uri.amap.com/marker?position=113.5630,22.2370&name=野狸岛",
    },
    {
        "name": "珠海大剧院观景台",
        "lat": 22.2385,
        "lon": 113.5655,
        "facing_azimuth_min": 250,
        "facing_azimuth_max": 290,
        "description": "日月贝高处观景平台，俯瞰海面日落，视野极佳",
        "best_seasons": json.dumps(["all"]),
        "tags": json.dumps(["高处俯瞰", "建筑前景", "海景"]),
        "map_url": "https://uri.amap.com/marker?position=113.5655,22.2385&name=珠海大剧院观景台",
    },
]


async def seed() -> None:
    await init_db()
    from sqlalchemy import select
    async with async_session() as session:
        for loc_data in LOCATIONS:
            stmt = select(ShootingLocation).where(ShootingLocation.name == loc_data["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(ShootingLocation(**loc_data))
        await session.commit()
    print(f"Seeded {len(LOCATIONS)} shooting locations.")


if __name__ == "__main__":
    asyncio.run(seed())
