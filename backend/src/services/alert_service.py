from src.db.models.user import UserProfile
from src.integrations.weather.open_meteo import get_current_and_forecast
from src.services.advisory_service import parse_lat_lon, split_crops


def _crop_phrase(profile: UserProfile) -> str:
    crops = split_crops(profile.crops_grown)
    if not crops:
        return "your crops"
    if len(crops) == 1:
        return crops[0]
    return ", ".join(crops[:2])


def _risk_date(day: dict) -> str:
    return str(day.get("date") or "one of the next days")


def _add_alert(
    alerts: list[dict],
    *,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    action_text: str,
) -> None:
    alerts.append(
        {
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "action_text": action_text,
        }
    )


def build_weather_alerts(profile: UserProfile) -> tuple[str, dict, list[dict]]:
    coords = parse_lat_lon(profile.location)
    if not coords:
        raise ValueError("No valid coordinates found. Save location as 'lat,lon' in profile.")

    lat, lon = coords
    location_used = profile.location or f"{lat},{lon}"
    raw_weather = get_current_and_forecast(lat, lon, forecast_days=5)
    crop_text = _crop_phrase(profile)
    forecast_days = raw_weather.get("forecast_days", [])
    alerts: list[dict] = []

    total_rain = 0.0
    dry_days = 0
    hottest_day: dict | None = None
    windiest_day: dict | None = None
    coldest_day: dict | None = None

    for day in forecast_days:
        rain = float(day.get("rain_mm") or 0)
        wind = float(day.get("wind_speed_kph") or 0)
        temp_max = day.get("temp_max_c")
        temp_min = day.get("temp_min_c")

        total_rain += rain
        if rain <= 0.5:
            dry_days += 1

        if hottest_day is None or float(temp_max or -999) > float(hottest_day.get("temp_max_c") or -999):
            hottest_day = day
        if windiest_day is None or wind > float(windiest_day.get("wind_speed_kph") or 0):
            windiest_day = day
        if coldest_day is None or float(temp_min or 999) < float(coldest_day.get("temp_min_c") or 999):
            coldest_day = day

        if rain >= 20:
            _add_alert(
                alerts,
                alert_type="heavy_rain",
                severity="high",
                title=f"Heavy rain expected on {_risk_date(day)}",
                message=f"Heavy rain may affect {crop_text} and field work.",
                action_text=(
                    "Clear drainage paths, avoid fertilizer application before the rain, "
                    "and delay spraying chemicals until the weather is calmer."
                ),
            )
        elif rain >= 10:
            _add_alert(
                alerts,
                alert_type="moderate_rain",
                severity="medium",
                title=f"Rain expected on {_risk_date(day)}",
                message=f"Rain is likely, so plan farm work for {crop_text} carefully.",
                action_text=(
                    "Apply fertilizer only if the rain is light, protect harvested crops, "
                    "and avoid spraying during rainfall."
                ),
            )

    if total_rain >= 45:
        _add_alert(
            alerts,
            alert_type="wet_week",
            severity="high",
            title="Very wet 5-day forecast",
            message="The next few days may bring a lot of rain.",
            action_text=(
                "Watch for waterlogging, improve drainage, and check crops for fungal disease signs "
                "after the rainy days."
            ),
        )

    if windiest_day and float(windiest_day.get("wind_speed_kph") or 0) >= 35:
        _add_alert(
            alerts,
            alert_type="strong_wind",
            severity="medium",
            title=f"Strong wind risk on {_risk_date(windiest_day)}",
            message="Strong wind can damage weak plants and reduce spraying quality.",
            action_text="Support young plants where possible and avoid pesticide or fertilizer spraying during strong wind.",
        )

    if hottest_day and float(hottest_day.get("temp_max_c") or 0) >= 32:
        severity = "high" if float(hottest_day.get("temp_max_c") or 0) >= 35 else "medium"
        _add_alert(
            alerts,
            alert_type="high_temperature",
            severity=severity,
            title=f"Hot weather expected on {_risk_date(hottest_day)}",
            message=f"High temperature may stress {crop_text}, especially young plants.",
            action_text="Water early morning or evening, use mulch if available, and avoid transplanting at midday.",
        )

    if coldest_day and float(coldest_day.get("temp_min_c") or 99) <= 5:
        _add_alert(
            alerts,
            alert_type="low_temperature",
            severity="medium",
            title=f"Cold night risk on {_risk_date(coldest_day)}",
            message="Low temperature may slow crop growth or stress seedlings.",
            action_text="Protect seedlings where possible and avoid watering late in the evening.",
        )

    if dry_days >= 4 and total_rain <= 2:
        _add_alert(
            alerts,
            alert_type="dry_spell",
            severity="medium",
            title="Dry days ahead",
            message=f"Very little rain is expected for {crop_text} in the next 5 days.",
            action_text="Plan irrigation if available, keep soil covered with mulch, and avoid unnecessary weeding under strong heat.",
        )

    if not alerts:
        _add_alert(
            alerts,
            alert_type="weather_clear",
            severity="low",
            title="No major weather risk found",
            message="The next 5 days do not show a major weather danger for your farm.",
            action_text="Continue normal farm work, but check alerts again before fertilizer application or spraying.",
        )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: severity_order.get(item["severity"], 3))
    return location_used, raw_weather, alerts[:5]
