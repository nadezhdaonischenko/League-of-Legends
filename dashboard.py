import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
import sys
from datetime import datetime, timedelta

# Подлючаем базу данных
load_dotenv()

DB_USER = "postgres"
DB_PASSWORD = os.getenv("parole_postgresql", "")
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "lol_db"

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Инициализируем Dash-приложение с темной темой
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

app.layout = dbc.Container([

    # Заголовок
    dbc.Row([
        dbc.Col(
            html.H1(
                "Riot Games API: Интерактивный Дашборд",
                className="text-center text-info my-4 font-weight-bold"
            ),
            width=12
        )
    ]),

    # KPI карточки
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(id="total-players", className="text-center text-info"),
                    html.P("Игроков", className="text-center")
                ])
            ])
        ], md=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(id="total-matches", className="text-center text-success"),
                    html.P("Матчей", className="text-center")
                ])
            ])
        ], md=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(id="avg-winrate", className="text-center text-warning"),
                    html.P("Средний винрейт", className="text-center")
                ])
            ])
        ], md=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(id="avg-duration", className="text-center text-danger"),
                    html.P("Средняя длительность", className="text-center")
                ])
            ])
        ], md=3)

    ], className="mb-4"),

    # Фильтр региона
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label(
                        "Выберите регион для анализа:",
                        className="text-info font-weight-bold mb-2"
                    ),

                    dcc.Dropdown(
                        id='region-dropdown',
                        options=[
                            {'label': 'Все регионы (Европа & США)', 'value': 'both'},
                            {'label': 'Europe West (EUW1)', 'value': 'euw1'},
                            {'label': 'North America (NA1)', 'value': 'na1'}
                        ],
                        value='both',
                        clearable=False,
                        style={'color': '#000'}
                    )
                ])
            ], className="mb-4 bg-secondary text-white")
        ], width=12)
    ]),

    # Фильтр периода
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label(
                        "Выберите период анализа:",
                        className="text-info font-weight-bold mb-2"
                    ),
                    dcc.Dropdown(
                        id='period-dropdown',
                        options=[
                            {'label': 'Последний снимок', 'value': 'latest'},
                            {'label': 'Текущий месяц', 'value': 'current_month'},
                            {'label': 'Последние 30 дней', 'value': 'last_30_days'},
                            {'label': 'Все время', 'value': 'all'}
                        ],
                        value='latest',
                        clearable=False,
                        style={'color': '#000'}
                    )
                ])
            ], className="mb-4 bg-secondary text-white")
        ], width=12)
    ]),

    # Графики
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='top-champions-chart')
                ])
            ], className="mb-4")
        ], lg=6, md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='lp-distribution-chart')
                ])
            ], className="mb-4")
        ], lg=6, md=12)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='match-duration-chart')
                ])
            ], className="mb-4")
        ], lg=6, md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='kd-scatter-chart')
                ])
            ], className="mb-4")
        ], lg=6, md=12)
    ])

], fluid=True)


@app.callback(
    [
        Output('top-champions-chart', 'figure'),
        Output('lp-distribution-chart', 'figure'),
        Output('match-duration-chart', 'figure'),
        Output('kd-scatter-chart', 'figure'),

        Output('total-players', 'children'),
        Output('total-matches', 'children'),
        Output('avg-winrate', 'children'),
        Output('avg-duration', 'children')
    ],
    [
    Input('region-dropdown', 'value'),
    Input('period-dropdown', 'value')
    ]
    )
def update_dashboard(selected_region, selected_period):

    # Пустые графики по умолчанию
    empty_fig = go.Figure()
    empty_fig.update_layout(
        title="Нет данных",
        template="plotly_dark"
    )

    fig1 = empty_fig
    fig2 = empty_fig
    fig3 = empty_fig
    fig4 = empty_fig

    # KPI по умолчанию
    total_players = "0"
    total_matches = "0"
    avg_winrate = "0%"
    avg_duration = "0 мин"

    # Чтение файлов
    try:
        df_lp = pd.read_sql("SELECT * FROM dashboard_lp_distribution", engine)
        df_champions = pd.read_sql("SELECT * FROM dashboard_champions_by_region", engine)
        df_matches = pd.read_sql("SELECT * FROM dashboard_matches_durations", engine)
        df_players = pd.read_sql("""SELECT * FROM players_daily""", engine)

    except Exception as e:
        print(
            f"\n[КРИТИЧЕСКАЯ ОШИБКА ДАШБОРДА]: {e}",
            file=sys.stderr
        )

        return (
            fig1,
            fig2,
            fig3,
            fig4,
            total_players,
            total_matches,
            avg_winrate,
            avg_duration
        )
    
    df_players["snapshot_date"] = pd.to_datetime(
    df_players["snapshot_date"]
    )

    df_champions["snapshot_date"] = pd.to_datetime(
    df_champions["snapshot_date"]
    )

    # Фильтрация периода

    today = pd.Timestamp.today().normalize()

    if selected_period == "latest":

        latest_snapshot = df_players["snapshot_date"].max()

        df_players = (
            df_players[
                df_players["snapshot_date"] == latest_snapshot
            ]
        )

        df_champions = (
            df_champions[
                df_champions["snapshot_date"] == latest_snapshot
        ]
        )

    elif selected_period == "current_month":

        start_month = pd.Timestamp(
            year=today.year,
            month=today.month,
            day=1
        )

        df_players = (
            df_players[
                df_players["snapshot_date"] >= start_month
            ]
        )

        df_champions = (
            df_champions[
                df_champions["snapshot_date"] >= start_month
            ]
        )

    elif selected_period == "last_30_days":

        start_date = today - pd.Timedelta(days=30)

        df_players = (
            df_players[
                df_players["snapshot_date"] >= start_date
            ]
        )

        df_champions = (
            df_champions[
                df_champions["snapshot_date"] >= start_date
            ]
        )

    # Фильтрация региона
    if selected_region != "both":

        if "region" in df_lp.columns:
            df_lp = df_lp[
                df_lp["region"] == selected_region
            ]

        if "region" in df_matches.columns:
            df_matches = df_matches[
                df_matches["region"] == selected_region
            ]

        if "region" in df_champions.columns:
            df_champions = df_champions[
                df_champions["region"] == selected_region
            ]

        if "region" in df_players.columns:
            df_players = df_players[
                df_players["region"] == selected_region
            ]

    # KPI карточки
    total_players = str(len(df_players))

    total_matches = str(df_matches["match_id"].nunique())

    avg_winrate = (
        f"{df_players['winrate'].mean():.1f}%"
        if not df_players.empty
        else "0%"
    )

    avg_duration = (
        f"{df_matches['game_duration_min'].mean():.1f} мин"
        if not df_matches.empty
        else "0 мин"
    )

    # --- [График 1] Топ-15 чемпионов ---
    try:
        if (
            not df_champions.empty
            and "matches_count" in df_champions.columns
        ):

            if selected_region == "both":

                top_15 = (
                    df_champions
                    .groupby("champion_name")
                    .agg(
                        matches_count=("matches_count", "sum"),
                        wins=("wins", "sum")
                    )
                    .reset_index()
                    )

                top_15["winrate"] = round(top_15["wins"] / top_15["matches_count"] * 100, 2)

            else:
                top_15 = df_champions.copy()

            top_15 = (
                top_15
                .sort_values(by="matches_count", ascending=False)
                .head(15)
                .sort_values(by="winrate", ascending=True)
            )

            fig1 = px.bar(
                top_15,
                x="winrate",
                y="champion_name",
                orientation="h",
                color="matches_count",
                title="Топ-15 чемпионов по винрейту",
                labels={
                    "winrate": "Винрейт (%)",
                    "champion_name": "Чемпион",
                    "matches_count": "Сыграно матчей"
                },
                template="plotly_dark"
            )
            fig1.update_xaxes(range=[45, 55]) 
    except Exception as e:
        print(f"Ошибка построения Графика 1 (Топ чемпионов): {e}", file=sys.stderr)

    # --- [График 2] Гистограмма LP ---
    try:
        if not df_lp.empty and 'league_points' in df_lp.columns:
            fig2 = px.histogram(
                df_lp, 
                x='league_points', 
                color='tier',
                nbins=10, 
                barmode='group',
                title="Распределение очков лиги (LP)",
                labels={
                    'league_points': 'Текущие LP', 
                    'count': 'Количество игроков', 
                    'tier': 'Ранг'},
                template='plotly_dark'
            )
    except Exception as e:
        print(f"Ошибка построения Графика 2 (Гистограмма LP): {e}", file=sys.stderr)

    # --- [График 3] Диаграмма размаха матчей ---
    try:
        if not df_matches.empty and 'game_duration_min' in df_matches.columns:
            x_col = 'region' if selected_region == 'both' and 'region' in df_matches.columns else ('tier' if 'tier' in df_matches.columns else None)
            fig3 = px.box(
                df_matches, 
                x=x_col, 
                y='game_duration_min',
                points="outliers",
                title="Длительность матчей по регионам",
                labels={
                    'game_duration_min': 'Время игры (мин)', 
                    'region': 'Регион', 
                    'tier': 'Ранг'},
                color=x_col,
                template='plotly_dark'
            )
    except Exception as e:
        print(f"Ошибка построения Графика 3 (Box-plot длительности): {e}", file=sys.stderr)

    # --- [График 4] Карта стилей чемпионов (Scatter) ---
    try:
        if not df_champions.empty and 'avg_deaths' in df_champions.columns and 'avg_kills' in df_champions.columns:
            fig4 = px.scatter(
                df_champions, 
                x='avg_deaths', 
                y='avg_kills',
                size='matches_count',
                color='winrate',
                size_max=18,
                hover_name='champion_name',
                title="Убийства и смерти чемпионов",
                labels={
                    'avg_deaths': 'Смерти', 
                    'avg_kills': 'Убийства',
                    "winrate": "WR (%)"
                    },
                template='plotly_dark',
                color_continuous_scale='Viridis'
            )
            
            fig4.update_layout(
                legend=dict(
                orientation="h",
                y=-0.25
                )
            )
            
            max_val = max(df_champions['avg_deaths'].max(), df_champions['avg_kills'].max())
            fig4.add_trace(
                go.Scatter(x=[0, max_val], y=[0, max_val], mode='lines', 
                           name='Линия KDA 1.0', line=dict(dash='dash', color='orange'))
            )
    except Exception as e:
        print(f"Ошибка построения Графика 4 (Scatter-plot): {e}", file=sys.stderr)

    return (
    fig1,
    fig2,
    fig3,
    fig4,
    str(total_players),
    str(total_matches),
    str(avg_winrate),
    str(avg_duration)
    )


if __name__ == '__main__':
    app.run(debug=True, port=8050)
