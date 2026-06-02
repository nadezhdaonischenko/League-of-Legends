# ====================================================
# АНАЛИЗ ОПРЕДЕЛЕННОГО ИГРОКА
# ====================================================

import pandas as pd

from riot_pipeline import (
    RiotDataPipeline,
    get_current_month_timestamps
)

REGIONS = {
    "euw1": "europe",
    "eun1": "europe",
    "ru": "europe",
    "tr1": "europe",
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "kr": "asia",
    "jp1": "asia",
    "tw2": "asia",
    "sg2": "asia"
}


def analyze_star_player(
    star_name: str,
    star_tag: str,
    star_home_platform: str
) -> pd.DataFrame:
    """
    Анализ активности игрока Riot по всем глобальным кластерам.
    """

    print("\n=== Анализ звездного игрока ===")

    start_ts, end_ts = get_current_month_timestamps()

    star_home_cluster = REGIONS.get(star_home_platform, "europe")

    print(
        f"Поиск игрока "
        f"{star_name}#{star_tag} "
        f"({star_home_platform.upper()})"
    )

    star_pipeline = RiotDataPipeline(platform_id=star_home_platform, cluster_override=star_home_cluster)

    star_puuid = star_pipeline.fetch_puuid_by_riot_id(star_name, star_tag)

    if not star_puuid:
        print("Игрок не найден.")
        return pd.DataFrame()

    print(
        f"Игрок найден. "
        f"PUUID: {star_puuid[:12]}..."
    )

    pipeline_asia = RiotDataPipeline(platform_id="kr", cluster_override="asia")

    pipeline_europe = RiotDataPipeline(platform_id="euw1", cluster_override="europe")

    pipeline_americas = RiotDataPipeline(platform_id="na1", cluster_override="americas")

    print("Сбор матчей по кластерам...")

    matches_asia = pipeline_asia.fetch_player_matches(
        star_puuid,
        start_ts,
        end_ts,
        count=100
    )

    matches_europe = pipeline_europe.fetch_player_matches(
        star_puuid,
        start_ts,
        end_ts,
        count=100
    )

    matches_americas = pipeline_americas.fetch_player_matches(
        star_puuid,
        start_ts,
        end_ts,
        count=100
    )

    count_asia = len(matches_asia)
    count_europe = len(matches_europe)
    count_americas = len(matches_americas)

    total_games = (
        count_asia +
        count_europe +
        count_americas
    )

    star_row = {
        "riot_id": f"{star_name}#{star_tag}",
        "puuid": star_puuid,
        "home_platform": star_home_platform.upper(),
        "home_cluster": star_home_cluster.upper(),
        "games_in_asia_cluster": count_asia,
        "games_in_europe_cluster": count_europe,
        "games_in_americas_cluster": count_americas,
        "total_games_this_month": total_games
    }

    df_star = pd.DataFrame([star_row])

    print("\n--- АНАЛИЗ АКТИВНОСТИ ИГРОКА ПО КЛАСТЕРАМ RIOT ---")
    print(
        f"Игрок: {star_name}#{star_tag} | "
        f"Домашний регион: {star_home_platform.upper()} "
        f"({star_home_cluster.upper()})"
    )

    print(f" ├─ Матчей в Азии (ASIA):         {count_asia}")
    print(f" ├─ Матчей в Европе (EUROPE):     {count_europe}")
    print(f" └─ Матчей в Америке (AMERICAS):  {count_americas}")

    print(
        f"Общая активность за текущий месяц: "
        f"{total_games} матчей."
    )

    return df_star


if __name__ == "__main__":

    df = analyze_star_player(star_name="Hide on bush", star_tag="KR", star_home_platform="kr") # Пример

# Сохранение результатов в CSV (опционально)
#    if not df.empty:
#        df.to_csv("star_player.csv", index=False, encoding="utf-8-sig")

#        print("\nФайл star_player.csv успешно сохранен.")
