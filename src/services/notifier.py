import hashlib
import hmac
import base64
import time
from datetime import datetime

import httpx

from src.config import settings
from src.schemas.sunset import SunsetForecast, LocationRecommendation


def _sign(secret: str) -> tuple[str, str]:
    """Compute Feishu webhook HMAC-SHA256 signature."""
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return timestamp, sign


def build_card_message(
    forecast: SunsetForecast,
    recommendations: list[LocationRecommendation],
) -> dict:
    """Build a Feishu interactive card message."""
    # Color based on quality
    quality = forecast.quality_value
    if quality >= 0.5:
        template = "red"
        level = "大烧"
    elif quality >= 0.2:
        template = "orange"
        level = "中烧"
    else:
        template = "blue"
        level = forecast.quality_label

    rec_text = ""
    for i, rec in enumerate(recommendations, 1):
        rec_text += f"**{i}. {rec.name}** — 朝向{rec.facing_azimuth:.0f}°，{rec.reason}\n"
        rec_text += f"　　建议到达：{rec.suggested_arrival}\n"

    if not rec_text:
        rec_text = "暂无推荐机位\n"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"珠海晚霞预警 - {level}",
                },
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**鲜艳度**\n{forecast.quality_value:.3f}（{forecast.quality_label}）",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**AOD**\n{forecast.aod_value:.3f}（{forecast.aod_label}）",
                            },
                        },
                    ],
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**事件**\n{forecast.event_name}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**数据源**\n{forecast.model}",
                            },
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**推荐拍摄机位**\n{rec_text}",
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"数据更新时间: {forecast.fetch_time.strftime('%Y-%m-%d %H:%M')}",
                        }
                    ],
                },
            ],
        },
    }
    return card


async def send_feishu_notification(
    forecast: SunsetForecast,
    recommendations: list[LocationRecommendation],
) -> bool:
    """Send notification via Feishu webhook. Returns True if sent successfully."""
    if not settings.feishu_webhook_url:
        return False

    card = build_card_message(forecast, recommendations)

    if settings.feishu_webhook_secret:
        timestamp, sign = _sign(settings.feishu_webhook_secret)
        card["timestamp"] = timestamp
        card["sign"] = sign

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.feishu_webhook_url, json=card)
            resp.raise_for_status()
            result = resp.json()
            return result.get("code") == 0 or result.get("StatusCode") == 0
    except Exception:
        return False
