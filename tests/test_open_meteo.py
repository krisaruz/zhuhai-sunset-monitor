from src.services.open_meteo import classify_aod, classify_quality, score_sunset


def test_clear_sky_scores_low():
    """全晴无云：没有散射介质，评分应很低。"""
    s = score_sunset([0, 0], [0, 0], [0, 0], [50, 50])
    assert s < 0.05


def test_ideal_midcloud_sunset():
    """理想晚霞：适量中云 + 少量卷云 + 无低云。"""
    s = score_sunset([5, 10], [50, 60], [30, 40], [60, 65])
    assert s > 0.5


def test_full_low_cloud_blocks():
    """低云全覆盖：挡光，评分应接近 0。"""
    s = score_sunset([95, 100], [50, 60], [30, 40], [60, 65])
    assert s < 0.1


def test_overcast_mid_cloud_penalty():
    """中云全覆盖（阴天）：评分应明显低于适量中云。"""
    s_ideal = score_sunset([5, 10], [50, 60], [30, 40], [60, 65])
    s_overcast = score_sunset([5, 10], [95, 100], [30, 40], [60, 65])
    assert s_overcast < s_ideal


def test_high_humidity_penalty():
    """高湿度浑浊天应比干爽天评分低。"""
    s_dry = score_sunset([5, 10], [50, 60], [30, 40], [55, 60])
    s_humid = score_sunset([5, 10], [50, 60], [30, 40], [92, 95])
    assert s_humid < s_dry


def test_score_always_in_range():
    """任意极端输入下评分都应落在 0~1。"""
    cases = [
        ([100, 100], [100, 100], [100, 100], [100, 100]),
        ([0, 0], [45, 45], [0, 0], [0, 0]),
        ([50, 50], [50, 50], [50, 50], [50, 50]),
    ]
    for low, mid, high, hum in cases:
        s = score_sunset(low, mid, high, hum)
        assert 0.0 <= s <= 1.0


def test_empty_input_returns_zero():
    assert score_sunset([], [], [], []) == 0.0


def test_classify_quality_boundaries():
    """烧级标签与 analyzer 历史口径一致。"""
    assert classify_quality(0.0) == "不烧"
    assert classify_quality(0.02) == "微烧"
    assert classify_quality(0.1) == "小烧"
    assert classify_quality(0.3) == "小烧到中烧"
    assert classify_quality(0.5) == "中等烧"
    assert classify_quality(0.7) == "中烧到大烧"
    assert classify_quality(0.9) == "大烧"


def test_classify_aod_boundaries():
    """AOD 标签按 sunsetbot 历史数据反推的阈值。"""
    assert classify_aod(0.15) == "水晶"
    assert classify_aod(0.25) == "还不错"
    assert classify_aod(0.35) == "一般"
    assert classify_aod(0.50) == "小污"
    assert classify_aod(0.60) == "污"
    assert classify_aod(0.70) == "大污"
    assert classify_aod(0.90) == "非常污"
