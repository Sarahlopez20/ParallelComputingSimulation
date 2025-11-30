import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parents[1]  # sube de /analysis/ a raíz
DB_PATH = BASE_DIR / "data" / "simulation.sqlite"

# Mapeo nombres → ISO-3
COUNTRY_ISO3 = {
    "Germany": "DEU",
    "France":  "FRA",
    "Italy":   "ITA",
    "Spain":   "ESP",
    "Sweden":  "SWE",
    "Belgium": "BEL",
    "UK":      "GBR",
}


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No se encuentra {DB_PATH.resolve()}")
    return sqlite3.connect(DB_PATH)


def build_time_series_df(conn):
    query = """
    SELECT
        m.day,
        c.name,
        m.healthy,
        m.infected,
        m.recovered,
        m.dead
    FROM metrics_per_country_day AS m
    JOIN country AS c ON c.country_id = m.country_id
    ORDER BY m.day, c.name;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        raise ValueError("No hay datos en metrics_per_country_day. ¿Has corrido la simulación?")

    df["total"] = df["healthy"] + df["infected"] + df["recovered"] + df["dead"]
    df["infected_pct"] = df["infected"] / df["total"] * 100
    df["infected_pct"] = df["infected_pct"].round(2)

    df["iso_code"] = df["name"].map(COUNTRY_ISO3)
    df = df.dropna(subset=["iso_code"])

    return df


def make_interactive_map(df):
    max_pct = df["infected_pct"].max()

    df["hover_text"] = (
        "Country: " + df["name"] +
        "<br>Day: " + df["day"].astype(str) +
        "<br>Infected: " + df["infected"].astype(str) +
        "<br>Total pop: " + df["total"].astype(str) +
        "<br><b>Infected %: " + df["infected_pct"].astype(str) + "%</b>"
    )

    fig = px.choropleth(
        df,
        locations="iso_code",
        color="infected_pct",
        hover_name="name",
        hover_data={"iso_code": False, "infected_pct": True, "hover_text": False},
        animation_frame="day",
        animation_group="name",
        color_continuous_scale="OrRd",   # escala rojiza más agradable
        range_color=(0, max_pct),
        scope="europe",
        labels={"infected_pct": "% infected", "day": "Day"},
        title="Evolution of infection percentage in Europe",
    )

    # Usar el texto bonito para el hover
    fig.update_traces(hovertemplate="%{customdata[0]}")
    fig.update_traces(customdata=df[["hover_text"]])

    # Layout más limpio
    fig.update_layout(
        template="plotly_white",
        title={
            "text": "Evolution of infection percentage in Europe<br>"
                    "<span style='font-size:12px;'>Simulation of pandemic spread with travel policies and variant</span>",
            "x": 0.5,
            "xanchor": "center",
        },
        coloraxis_colorbar=dict(
            title="% infected",
            ticks="outside",
        ),
        margin=dict(l=20, r=20, t=80, b=20),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "buttons": [
                {
                    "label": "▶ Play",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 80, "redraw": True},
                                    "fromcurrent": True, "transition": {"duration": 50}}],
                },
                {
                    "label": "⏸ Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False},
                                      "mode": "immediate",
                                      "transition": {"duration": 0}}],
                },
            ],
            "x": 0.02,
            "y": 0.02,
        }],
    )

    # Slider un pelín más chulo
    fig.update_layout(
        sliders=[{
            "currentvalue": {
                "prefix": "Day: ",
                "font": {"size": 14}
            }
        }]
    )

    fig.write_html("interactive_map.html")
    print("✅ Mapa interactivo guardado en 'interactive_map.html'")


def main():
    conn = get_connection()
    try:
        df = build_time_series_df(conn)
        make_interactive_map(df)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
