import os
import time
from datetime import datetime, timezone, date
from wsgiref import headers
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from ratelimit import sleep_and_retry, limits
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import MetaData, Table

# ====================================================
# 1. НАСТРОЙКА ОКРУЖЕНИЯ
# ====================================================
load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY", "").strip()

if not API_KEY:
    raise ValueError("Критическая ошибка: Добавьте RIOT_API_KEY в файл .env")

REGION_MAPPING = {"euw1": "europe", "na1": "americas"}
TIERS = ["challenger", "grandmaster", "master"]

# ==================================================== 
# 2. РАБОТА С RIOT DATA DRAGON 
# ==================================================== 
def generate_champions_dictionary(): 
    """ Скачиваем актуальный патч, создаем файл champions.csv и возвращаем словарь: 
        {int(ID): {"name": Имя, "tags": Теги, "title": Титул}} 
    """ 
    print("Загрузка статических данных из Riot Data Dragon...") 
    
    headers = { 
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/120.0.0.0 Safari/537.36"
        ) 
    }
    
    try: 
    # Получаем список актуальных версий игры 
        version_res = requests.get(
            "https://ddragon.leagueoflegends.com/api/versions.json", 
            headers=headers, 
            timeout=10) 
        version_res.raise_for_status() 
        latest_version = version_res.json()[0] 
        print(f"Актуальный патч Data Dragon: {latest_version}") 
    
        # Загружаем справочник чемпионов 
        champions_url = (
            f"https://ddragon.leagueoflegends.com/cdn/" 
            f"{latest_version}/data/en_US/champion.json") 
    
        response = requests.get(champions_url, headers=headers, timeout=10) 
        response.raise_for_status() 
        champions_data = response.json().get("data", {}) 
        champions_rows = [] 
        champion_map = {} 
    
        for champ_name, champ_info in champions_data.items(): 
            champ_id = int(champ_info["key"]) 
            tags_str = ",".join(champ_info["tags"]) 
            champions_rows.append({
                "champion_id": champ_id, 
                "champion_name": champ_name, 
                "title": champ_info["title"], 
                "tags": tags_str 
                }) 
            champion_map[champ_id] = {
                "name": champ_name, 
                "tags": tags_str, 
                "title": champ_info["title"]
                } 
        champions_df = pd.DataFrame(champions_rows) 

        print(
            f"Успешно сохранен справочник: champions.csv " 
            f"(Размер: {champions_df.shape})" 
            ) 
        return champion_map
         
    except Exception as e: 
        print(f"Ошибка обработки Data Dragon ({e}), используем числовые ID.") 
    return {}

# ====================================================
# 2. ЗАЩИТА ОТ RATE LIMITS
# ====================================================

session = requests.Session()
session.headers.update({
    "X-Riot-Token": API_KEY
})

@sleep_and_retry
@limits(calls=90, period=120)
def rate_limited_get(url, params=None, max_retries=5):
    for attempt in range(max_retries):
        # ~15 запросов/сек (безопасно относительно лимита Riot)
        time.sleep(0.07)

        try:
            response = session.get(url, params=params, timeout=15)
            # Riot API rate limit
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 10))

                print(f"\n[Riot API] Лимит исчерпан. Ожидание {retry_after} сек...")
                
                time.sleep(retry_after)
                continue

            # Временные ошибки сервера Riot
            if response.status_code in (500, 502, 503, 504):
                wait_time = 2 ** attempt
                print(f"\n[Riot API] Ошибка. {response.status_code}. Повтор через {wait_time} сек...")
                time.sleep(wait_time)
                continue

            return response

        except requests.exceptions.Timeout:
            print("\n[Ошибка] Таймаут запроса")
        except requests.exceptions.ConnectionError:
            print("\n[Ошибка] Нет соединения")
        except Exception as e:
            print(f"\n[Ошибка сети]: {e}")
        time.sleep(2)
    return None

def get_current_month_timestamps():
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end_of_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_of_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return int(start_of_month.timestamp()), int(end_of_month.timestamp())

# ====================================================
# 3. КЛАСС СБОРЩИКА ДАННЫХ
# ====================================================

class RiotDataPipeline:
    def __init__(self, platform_id, cluster_override=None):
        self.platform_id = platform_id
        self.cluster_id = cluster_override or REGION_MAPPING.get(platform_id)
        if not self.cluster_id:
            raise ValueError(f"Неизвестный регион: {platform_id}")
        self.platform_url = f"https://{platform_id}.api.riotgames.com"
        self.cluster_url = f"https://{self.cluster_id}.api.riotgames.com"

    def fetch_puuid_by_riot_id(self, game_name, tag_line):
        url = f"{self.cluster_url}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        res = rate_limited_get(url)
        if not res or res.status_code != 200:
            print(f"Игрок {game_name}#{tag_line} не найден на кластере {self.cluster_id}")
            return None
        return res.json().get("puuid")

    def fetch_leagues_entries(self, tier):
        url = f"{self.platform_url}/lol/league/v4/{tier}leagues/by-queue/RANKED_SOLO_5x5"
        res = rate_limited_get(url)
        if not res or res.status_code != 200:
            return []
        return res.json().get("entries", [])

    def fetch_summoner_by_puuid(self, puuid):
        url = f"{self.platform_url}/lol/summoner/v4/summoners/by-puuid/{puuid}"
        res = rate_limited_get(url)
        return res.json() if res and res.status_code == 200 else None

    def fetch_player_matches(self, puuid, start_time, end_time, count=5):
        url = f"{self.cluster_url}/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params = {"startTime": start_time, "endTime": end_time, "queue": 420, "start": 0, "count": count}
        res = rate_limited_get(url, params=params)
        return res.json() if res and res.status_code == 200 else []

    def fetch_match_details(self, match_id):
        url = f"{self.cluster_url}/lol/match/v5/matches/{match_id}"
        res = rate_limited_get(url)
        return res.json() if res and res.status_code == 200 else None

# ====================================================
# 4. ПОДКЛЮЧЕНИЕ К POSTGRESQL
# ====================================================
 
DB_USER = "postgres" 
DB_PASSWORD = os.getenv("parole_postgresql", "")
DB_HOST = "localhost" 
DB_PORT = "5432" 
DB_NAME = "lol_db" 

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}" )

with engine.begin() as conn:
    conn.execute(
        text("DELETE FROM players_daily WHERE snapshot_date = CURRENT_DATE")
    )

    conn.execute(
        text("DELETE FROM champions_daily WHERE snapshot_date = CURRENT_DATE")
    )

def upsert_dataframe(df, table_name, engine, conflict_columns):
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)

    records = df.to_dict(orient="records")

    if not records:
        return

    stmt = insert(table).values(records)

    stmt = stmt.on_conflict_do_nothing(
        index_elements=conflict_columns
    )

    with engine.begin() as conn:
        conn.execute(stmt)

# ====================================================
# 6. ГЛАВНЫЙ ЦИКЛ СБОРА И СВЯЗЫВАНИЯ ТАБЛИЦ
# ====================================================

def main():
    champion_map = generate_champions_dictionary()
    start_ts, end_ts = get_current_month_timestamps()
    
    raw_matches_list = []
    raw_participants_list = []
    players_registry = {} 
    team_id_to_name = {100: "Blue", 200: "Red"}

    # --- ОБЩИЙ СБОР РЕГИОНОВ ПО ТЗ ---
    print("\n=== Шаг 2: Общий сбор базовой информации по регионам ===")
    platforms = ["euw1", "na1"]
    for platform in platforms:
        pipeline = RiotDataPipeline(platform)
        for tier in TIERS:
            entries = pipeline.fetch_leagues_entries(tier)
            print(f"[{platform.upper()}] Найдено {len(entries)} игроков in лиге {tier.upper()}")
            
            for entry in entries[:20]:  # Топ-20 
                puuid = entry.get("puuid")
                if not puuid:
                    continue
                
                summoner_data = pipeline.fetch_summoner_by_puuid(puuid)
                # ДЛЯ УБОРКИ UNKNOWN: 
                # Если сервер Riot отдал имя — берем его. 
                # Если сервер занят или лимит ключа исчерпан — генерируем красивый уникальный никнейм по ТЗ
                if summoner_data and summoner_data.get("name"):
                    real_name = summoner_data.get("name")
                else:
                    real_name = f"Summoner_{platform.upper()}_{puuid[:6]}"
                
                players_registry[puuid] = {
                    "puuid": puuid, 
                    "summoner_name": real_name, 
                    "region": platform, 
                    "tier": tier,
                    "league_points": entry.get("leaguePoints", 0), 
                    "wins_total": entry.get("wins", 0), 
                    "losses_total": entry.get("losses", 0),
                    "veteran": entry.get("veteran", False), 
                    "inactive": entry.get("inactive", False),
                    "fresh_blood": entry.get("freshBlood", False), 
                    "hot_streak": entry.get("hotStreak", False)
                }
                
                match_ids = pipeline.fetch_player_matches(puuid, start_ts, end_ts, count=100)
                print(f"Игрок {real_name} сыграл {len(match_ids)} матчей за месяц")
                
                for m_id in match_ids:
                    match_data = pipeline.fetch_match_details(m_id)
                    if not match_data:
                        continue
                        
                    info = match_data.get("info", {})
                    game_duration = info.get("gameDuration", 0)
                    
                    raw_matches_list.append({
                        "match_id": m_id, 
                        "region": platform, 
                        "tier": tier, 
                        "game_duration": game_duration,
                        "game_mode": info.get("gameMode"), 
                        "game_version": info.get("gameVersion"), 
                        "game_creation": info.get("gameCreation")
                    })
                    
                    winning_team_name = "Unknown"
                    for team in info.get("teams", []):
                        if team.get("win") == True:
                            winning_team_name = team_id_to_name.get(team.get("teamId"), "Unknown")
                    
                    for p in info.get("participants", []):
                        player_team_name = team_id_to_name.get(p.get("teamId"), "Unknown")
                        c_id = p.get("championId")
                        champ_info = champion_map.get(c_id, {"name": f"Unknown_{c_id}", "tags": "Unknown", "title": "Unknown"})

                        raw_participants_list.append({
                            "match_id": m_id,
                            "region": platform, 
                            "puuid": p.get("puuid"), 
                            "champion_name": champ_info["name"], 
                            "champion_id": c_id,
                            "champion_title": champ_info["title"], 
                            "champion_tags": champ_info["tags"], 
                            "team": player_team_name,
                            "winning_team": winning_team_name, 
                            "kills": p.get("kills", 0), 
                            "deaths": p.get("deaths", 0), 
                            "assists": p.get("assists", 0),
                            "gold_earned": p.get("goldEarned", 0), 
                            "damage_to_champions": p.get("totalDamageDealtToChampions", 0),
                            "minions_killed": p.get("totalMinionsKilled", 0), 
                            "vision_score": p.get("visionScore", 0), 
                            "win": p.get("win", False),
                            "role": p.get("role"), 
                            "team_position": p.get("teamPosition"), 
                            "game_duration_sec": game_duration
                        })

    snapshot_date = date.today()                   

    # Перевод в DataFrame
    df_raw_matches = pd.DataFrame(raw_matches_list).drop_duplicates(subset=["match_id"])
    df_raw_parts = pd.DataFrame(raw_participants_list)

    if df_raw_matches.empty or df_raw_parts.empty:
        print("Данные не собраны. Проверьте валидность API ключа.")
        return
    
    # 1. matches
    df_raw_matches["game_duration_min"] = round(df_raw_matches["game_duration"] / 60, 2)
    matches_cols = [
        "match_id", 
        "region", 
        "tier", 
        "game_duration", 
        "game_duration_min", 
        "game_mode", 
        "game_version", 
        "game_creation"]
    df_raw_matches = df_raw_matches[matches_cols]

    try: 
        upsert_dataframe(df_raw_matches, "matches", engine, ["match_id"]) 
        print("Таблица matches успешно загружена") 
    except Exception as e: 
        print(f"Ошибка при загрузке matches: {e}")

    # 2. participants 
    try:
        upsert_dataframe(df_raw_parts, "participants", engine, ["match_id", "puuid"])
        print("Таблица participants успешно загружена")
    except Exception as e:
        print(f"Ошибка при загрузке participants: {e}")

    print("\n=== Шаг 3: Обработка данных через Pandas ===")

    # 3. players
    player_monthly_stats = df_raw_parts[df_raw_parts["puuid"].isin(players_registry.keys())].groupby("puuid").agg(
        matches_this_month=("match_id", "count")
    ).reset_index()

    players_rows = []
    for puuid, meta in players_registry.items():
        monthly_m = player_monthly_stats[player_monthly_stats["puuid"] == puuid]
        matches_count = int(monthly_m["matches_this_month"].iloc[0]) if not monthly_m.empty else 0
        total_games = meta["wins_total"] + meta["losses_total"]
        winrate = round(meta["wins_total"] / total_games * 100, 2) if total_games > 0 else 0.0
        
        players_rows.append({
            "puuid": puuid, 
            "summoner_name": meta["summoner_name"], 
            "region": meta["region"], 
            "tier": meta["tier"],
            "league_points": meta["league_points"], 
            "wins": meta["wins_total"], 
            "losses": meta["losses_total"], 
            "winrate": winrate,
            "matches_played_month": matches_count, 
            "is_veteran": meta["veteran"], 
            "is_inactive": meta["inactive"],
            "is_fresh_blood": meta["fresh_blood"], 
            "is_hot_streak": meta["hot_streak"]
        })
    df_players = pd.DataFrame(players_rows)
    df_players["snapshot_date"] = snapshot_date

    try: 
        df_players.to_sql("players_daily", engine, if_exists="append", index=False) 
        print("Таблица players успешно загружена") 
    except Exception as e: 
        print(f"Ошибка при загрузке players: {e}")

    # Вычисление KDA
    safe_deaths = np.maximum(df_raw_parts["deaths"], 1)
    df_raw_parts["kda"] = (df_raw_parts["kills"] + df_raw_parts["assists"]) / safe_deaths

    # 4. champions
    df_champions = df_raw_parts.groupby("champion_name").agg(
        champion_id=("champion_id", "first"),         
        champion_title=("champion_title", "first"),   
        champion_tags=("champion_tags", "first"),     
        matches_count=("match_id", "count"),          
        wins=("win", "sum"),                          
        avg_kills=("kills", "mean"),
        avg_deaths=("deaths", "mean"),
        avg_assists=("assists", "mean"),
        avg_kda=("kda", "mean"),                      
        avg_gold_earned=("gold_earned", "mean"),
        avg_damage=("damage_to_champions", "mean"),
        avg_minions_killed=("minions_killed", "mean"),
        avg_vision_score=("vision_score", "mean")
    ).reset_index()

    df_champions["losses"] = df_champions["matches_count"] - df_champions["wins"]
    df_champions["winrate"] = round((df_champions["wins"] / df_champions["matches_count"]) * 100, 2)

    avg_cols = [col for col in df_champions.columns if col.startswith("avg_") or col == "winrate"]
    df_champions[avg_cols] = df_champions[avg_cols].round(2)

    final_cols = [
        "champion_id", 
        "champion_name", 
        "champion_title", 
        "champion_tags",
        "matches_count", 
        "wins", 
        "losses", 
        "winrate",
        "avg_kills", 
        "avg_deaths", 
        "avg_assists", 
        "avg_kda", 
        "avg_gold_earned", 
        "avg_damage", 
        "avg_minions_killed", 
        "avg_vision_score"
    ]
    df_champions = df_champions[final_cols]
    df_champions["snapshot_date"] = snapshot_date

    try: 
        df_champions.to_sql("champions_daily", engine, if_exists="append", index=False) 
        print("Таблица champions успешно загружена") 
    except Exception as e: 
        print(f"Ошибка при загрузке champions: {e}")    
    

    # --- ФИНАЛЬНЫЙ АНАЛИТИЧЕСКИЙ ОТЧЕТ В КОНСОЛЬ ---
    print("\n--- ТОП-10 ЧЕМПИОНОВ С НАИВЫСШИМ СРЕДНИМ KDA ---")
    top_10_kda = df_champions.sort_values(by="avg_kda", ascending=False).head(10)
    print(top_10_kda[["champion_name", "champion_title", "matches_count", "avg_kda"]].to_string(index=False))

    print("\n--- ЧЕМПИОН-ЛИДЕР ПО КОЛИЧЕСТВУ СЫГРАННЫХ МАТЧЕЙ ---")
    popular_champ = df_raw_parts["champion_name"].value_counts().sort_values(ascending=False).head(1)
    print(f"Самый популярный чемпион месяца: {popular_champ.index[0]} (Сыграно игр: {popular_champ.values[0]})")

    print("\n--- СРЕДНЯЯ ДЛИТЕЛЬНОСТЬ МАТЧЕЙ ---")
    avg_duration_min = round(df_raw_matches["game_duration_min"].mean(), 2)
    print(f"Средняя длительность матча за текущий месяц: {avg_duration_min} минут")

    print("\n--- ТОП-5 ИГРОКОВ ПО КОЛИЧЕСТВУ ОЧКОВ ЛИГИ (LP) ---")
    top_5_players = df_players.sort_values(by="league_points", ascending=False).head(5)
    print(top_5_players[["summoner_name", "region", "tier", "league_points", "winrate"]].to_string(index=False))

    print("\n=== Все локальные файлы и справочники созданы и готовы! ===")

def run_pipeline():
    main()

if __name__ == "__main__":
    run_pipeline()
