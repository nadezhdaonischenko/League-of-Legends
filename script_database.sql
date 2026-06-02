-- Создаем чистую базу данных

CREATE DATABASE lol_db;

-- Создание таблиц баз данных

CREATE TABLE participants (
    id SERIAL PRIMARY KEY,                        -- Внутренний ID записи
    match_id VARCHAR(50) NOT NULL,                -- ID матча (например, "RU_12345")
    region VARCHAR(10),                           -- Платформа/регион (например, "ru1")
    puuid VARCHAR(100),                           -- Уникальный ID игрока Riot
    id SERIAL PRIMARY KEY,                        -- Внутренний ID записи
    match_id VARCHAR(50) NOT NULL,                -- ID матча (например, "RU_12345")
    region VARCHAR(10),                           -- Платформа/регион (например, "ru1")
    puuid VARCHAR(100),                           -- Уникальный ID игрока Riot
    champion_name VARCHAR(50),                    -- Имя чемпиона (например, "Ahri")
    champion_id INT,                              -- Числовой ID чемпиона
    champion_title VARCHAR(100),                  -- Титул (например,"the Nine-Tailed Fox")
    champion_tags TEXT,                           -- Массив тегов (ролей) чемпиона
    team VARCHAR(20),                             -- Команда игрока ("Red" / "Blue")
    winning_team VARCHAR(20),                     -- Победившая команда
    kills INT DEFAULT 0,                          -- Количество убийств игрока (Kills)
    deaths INT DEFAULT 0,                         -- Количество смертей игрока (Deaths)
    assists INT DEFAULT 0,                        -- Количество содействий игрока (Assists)
    gold_earned INT DEFAULT 0,                    -- Всего заработанного золота за матч
    damage_to_champions INT DEFAULT 0,            -- Суммарный нанесенный урон по чемпионам
    minions_killed INT DEFAULT 0,                 -- Количество убитых миньонов (CS / Creep Score)
    vision_score INT DEFAULT 0,                   -- Очки обзора (установка/уничтожение вардов)
    win BOOLEAN DEFAULT FALSE,                     -- True/False (выиграл ли конкретный игрок)
    role VARCHAR(30),                             -- Роль в матче (DUO, SOLO и т.д.)
    team_position VARCHAR(30),                    -- Позиция на карте (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY)
    game_duration_sec INT,                        -- Длительность матча в секундах
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Время добавления записи в БД
);

-- Индексы для быстрого поиска по популярным полям
CREATE INDEX idx_match_id ON participants(match_id);
CREATE INDEX idx_puuid ON participants(puuid);
CREATE INDEX idx_participants_champion ON participants(champion_id);
CREATE INDEX idx_participants_region ON participants(region);
CREATE INDEX idx_participants_team_position ON participants(team_position);

CREATE TABLE matches (
    match_id VARCHAR(50) PRIMARY KEY,             -- Уникальный ID матча (уникальный ключ)
    region VARCHAR(10) NOT NULL,                  -- Платформа/регион (например, "ru1")
    tier VARCHAR(20),                             -- Ранг матча (например, "DIAMOND", "CHALLENGER")
    game_duration INT,                            -- Длительность матча в секундах
    game_duration_min FLOAT,                      -- Длительность матча в минутах
    game_mode VARCHAR(30),                        -- Режим игры (CLASSIC, ARAM, URF)
    game_version VARCHAR(50),                     -- Патч/версия игры (например, "14.1.1")
    game_creation BIGINT,                         -- Дата создания матча (таймстамп в миллисекундах)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Время записи матча в вашу базу данных
);

-- Индекс для быстрой фильтрации по рангам и регионам
CREATE INDEX idx_matches_tier_region ON matches(tier, region);
CREATE INDEX idx_matches_creation ON matches(game_creation);

ALTER TABLE participants
ADD CONSTRAINT uq_match_player
UNIQUE (match_id, puuid);

ALTER TABLE participants
ADD CONSTRAINT fk_participants_match
FOREIGN KEY (match_id)
REFERENCES matches(match_id);

CREATE TABLE players_daily (
    snapshot_date DATE NOT NULL,                  -- Дата снятия метрик (для отслеживания истории)
    puuid VARCHAR(100) NOT NULL,                  -- Уникальный ID игрока Riot (не меняется при смене ника)

    summoner_name VARCHAR(100),                   -- Имя призывателя / никнейм игрока
    region VARCHAR(20),                           -- Игровой регион аккаунта (например, "ru", "euw1")
    tier VARCHAR(20),                             -- Ранг игрока (например, "DIAMOND", "CHALLENGER")

    league_points INTEGER,                        -- Очки лиги (LP / League Points)
    wins INTEGER,                                 -- Всего побед в текущем сезоне
    losses INTEGER,                               -- Всего поражений в текущем сезоне
    winrate NUMERIC(5,2),                         -- Процент побед (Winrate) в процентах (например, 55.45)

    matches_played_month INTEGER,                 -- Количество сыгранных матчей за последний месяц

    is_veteran BOOLEAN,                           -- Сыграл ли игрок более 100 матчей в этой лиге
    is_inactive BOOLEAN,                          -- Является ли игрок неактивным (давно не заходил в ранговые игры)
    is_fresh_blood BOOLEAN,                       -- Попал ли игрок в эту лигу недавно (новичок лиги)
    is_hot_streak BOOLEAN,                        -- Находится ли игрок на серии побед (3 или более побед подряд)

    PRIMARY KEY (snapshot_date, puuid)
);

CREATE INDEX idx_players_daily_region ON players_daily(region);
CREATE INDEX idx_players_daily_tier ON players_daily(tier);
CREATE INDEX idx_players_daily_date ON players_daily(snapshot_date);

CREATE TABLE champions_daily (
    snapshot_date DATE NOT NULL,                  -- Дата снятия метрик / агрегации данных
    champion_id INT NOT NULL,                     -- Числовой ID чемпиона в Riot API
    champion_name VARCHAR(100),                   -- Имя чемпиона (например, "Ahri", "Yasuo")
    champion_title VARCHAR(200),                  -- Титул чемпиона (например, "the Unforgiven")
    champion_tags TEXT,                           -- Массив тегов / основных ролей (например, "Mage, Assassin")

    matches_count INT,                            -- Общее количество сыгранных матчей с этим чемпионом
    wins INT,                                     -- Количество побед с этим чемпионом
    losses INT,                                   -- Количество поражений с этим чемпионом
    winrate NUMERIC(5,2),                         -- Процент побед чемпиона (Winrate, например 52.35)

    avg_kills NUMERIC(10,2),                      -- Среднее количество убийств за матч (Avg Kills)
    avg_deaths NUMERIC(10,2),                     -- Среднее количество смертей за матч (Avg Deaths)
    avg_assists NUMERIC(10,2),                    -- Среднее количество содействий за матч (Avg Assists)
    avg_kda NUMERIC(10,2),                        -- Средний коэффициент KDA ((Kills + Assists) / Deaths)

    avg_gold_earned NUMERIC(10,2),                -- Среднее количество заработанного золота за матч
    avg_damage NUMERIC(10,2),                     -- Средний нанесенный урон по чемпионам за матч
    avg_minions_killed NUMERIC(10,2),             -- Среднее количество убитых миньонов за матч (Avg CS)
    avg_vision_score NUMERIC(10,2),               -- Среднее количество очков обзора за матч

    PRIMARY KEY (snapshot_date, champion_id)
);

CREATE INDEX idx_champions_daily_date ON champions_daily(snapshot_date);
CREATE INDEX idx_champions_daily_name ON champions_daily(champion_name);

-- Создаем таблицы витрин

CREATE TABLE dashboard_region_summary (
    region VARCHAR(20) PRIMARY KEY,               -- Игровой регион (первичный ключ, например, "ru", "euw1")
    total_tracked_players INTEGER,                -- Общее количество отслеживаемых игроков в данном регионе
    avg_player_winrate NUMERIC(5,2),              -- Средний процент побед (Winrate) среди игроков региона
    avg_lp NUMERIC(10,2),                         -- Среднее количество очков лиги (Avg LP) по региону
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Время последнего обновления статистики региона
);

CREATE TABLE dashboard_lp_distribution (
    snapshot_date DATE,                           -- Дата создания снимка данных (день фиксации ранга)
    puuid VARCHAR(100),                           -- Уникальный ID игрока Riot (не меняется при смене ника)
    region VARCHAR(20),                           -- Игровой регион аккаунта (например, "ru", "euw1")
    tier VARCHAR(20),                             -- Ранг игрока на момент снимка (например, "DIAMOND", "MASTER")
    league_points INTEGER                         -- Количество очков лиги (LP) на момент снимка
);

CREATE INDEX idx_lp_distribution_snapshot
ON dashboard_lp_distribution(snapshot_date);

CREATE TABLE dashboard_champions_cleaned (
    snapshot_date DATE,                           -- Дата снятия метрик (день агрегации статистики)
    champion_id INTEGER,                          -- Числовой ID чемпиона в Riot API
    champion_name VARCHAR(100),                   -- Имя чемпиона (например, "Ahri", "Yasuo")
    matches_count INTEGER,                        -- Общее количество сыгранных матчей с этим чемпионом за день
    wins INTEGER,                                 -- Количество побед с этим чемпионом за день
    losses INTEGER,                               -- Количество поражений с этим чемпионом за день
    winrate NUMERIC(5,2),                         -- Процент побед чемпиона (Winrate, например 50.15)
    avg_kda NUMERIC(10,2)                         -- Средний коэффициент KDA за день ((Kills + Assists) / Deaths)
);

CREATE INDEX idx_dashboard_champion_snapshot
ON dashboard_champions_cleaned(snapshot_date);

CREATE TABLE dashboard_matches_durations (
    match_id VARCHAR(50),                         -- Уникальный ID матча в Riot API (например, "RU_12345")
    region VARCHAR(20),                           -- Игровой регион, в котором прошел матч (например, "ru", "euw1")
    tier VARCHAR(20),                             -- Средний ранг участников матча (например, "CHALLENGER")
    game_duration_min NUMERIC(10,2),              -- Длительность матча, конвертированная в минуты
    game_date TIMESTAMP                           -- Дата и время создания (начала) матча
);

CREATE TABLE dashboard_champions_by_region (
    snapshot_date DATE,                           -- Дата снятия метрик (день агрегации статистики)

    region VARCHAR(20),                           -- Игровой регион аналитики (например, "ru", "euw1")
    champion_name VARCHAR(100),                   -- Имя чемпиона (например, "Ahri", "Yasuo")

    matches_count INTEGER,                        -- Общее количество сыгранных матчей с чемпионом в этом регионе за день
    wins INTEGER,                                 -- Количество побед с этим чемпионом в указанном регионе
    winrate NUMERIC(5,2),                         -- Процент побед чемпиона в регионе (Winrate, например 51.20)

    avg_kills NUMERIC(10,2),                      -- Среднее количество убийств за матч в этом регионе (Avg Kills)
    avg_deaths NUMERIC(10,2),                     -- Среднее количество смертей за матч в этом регионе (Avg Deaths)
    avg_kda NUMERIC(10,2)                         -- Средний коэффициент KDA чемпиона в данном регионе за день
);

CREATE INDEX idx_dashboard_champion_region
ON dashboard_champions_by_region(region);

CREATE INDEX idx_dashboard_champion_region_date
ON dashboard_champions_by_region(snapshot_date);