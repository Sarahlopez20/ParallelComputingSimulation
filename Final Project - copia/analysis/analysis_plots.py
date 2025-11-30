import sqlite3
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parents[1]  # sube de /analysis/ a raíz
DB_PATH = BASE_DIR / "data" / "simulation.sqlite"


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No se encuentra la base de datos {DB_PATH.resolve()}")
    return sqlite3.connect(DB_PATH)


# ============================================================
# 1. Distribución de la edad de los fallecidos
#    (What is the distribution of the age of the deceased?)
# ============================================================
def plot_age_distribution_of_deceased(conn):
    query = """
    SELECT p.age
    FROM patient AS p
    JOIN patient_result AS pr ON p.patient_id = pr.patient_id
    WHERE pr.final_state = 'dead';
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[AGE] No hay fallecidos en la simulación.")
        return

    plt.figure()
    df["age"].hist(bins=15)
    plt.xlabel("Age")
    plt.ylabel("Number of deaths")
    plt.title("Distribution of age among deceased patients")
    plt.tight_layout()
    plt.savefig("plot_01_age_distribution_deceased.png")
    plt.close()
    print("[OK] plot_01_age_distribution_deceased.png")


# ============================================================
# 2. Gasto en vacunas y medicinas por país
#    (How much did each country spend on vaccines and medicine?)
# ============================================================
def plot_spending_by_country(conn):
    query = """
    SELECT c.name,
           b.total_vaccine_spend,
           b.total_medicine_spend,
           b.total_spend
    FROM country AS c
    JOIN budget AS b ON c.country_id = b.country_id;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[SPENDING] No hay datos en budget.")
        return

    df = df.set_index("name")

    # Grafico de barras apiladas: vacuna vs medicinas
    plt.figure()
    df[["total_vaccine_spend", "total_medicine_spend"]].plot(
        kind="bar", stacked=True
    )
    plt.xlabel("Country")
    plt.ylabel("Total spend")
    plt.title("Vaccine and medicine spending by country")
    plt.tight_layout()
    plt.savefig("plot_02_spending_vaccines_medicines_by_country.png")
    plt.close()
    print("[OK] plot_02_spending_vaccines_medicines_by_country.png")


# ============================================================
# 3. Porcentaje de infección por país
#    (Percentage of infection per country?)
# ============================================================
def plot_infection_percentage_by_country(conn):
    # Tomamos el último día disponible en metrics_per_country_day
    last_day_query = "SELECT MAX(day) AS max_day FROM metrics_per_country_day;"
    last_day = pd.read_sql_query(last_day_query, conn)["max_day"].iloc[0]

    query = """
    SELECT c.name,
           m.healthy,
           m.infected,
           m.recovered,
           m.dead
    FROM metrics_per_country_day AS m
    JOIN country AS c ON c.country_id = m.country_id
    WHERE m.day = ?;
    """
    df = pd.read_sql_query(query, conn, params=(last_day,))

    if df.empty:
        print("[INF PCT] No hay métricas para el último día.")
        return

    total = df[["healthy", "infected", "recovered", "dead"]].sum(axis=1)
    df["infected_pct"] = df["infected"] / total * 100

    plt.figure()
    df.plot(x="name", y="infected_pct", kind="bar", legend=False)
    plt.xlabel("Country")
    plt.ylabel("Infected (%)")
    plt.title(f"Percentage of infected population per country (day {last_day})")
    plt.tight_layout()
    plt.savefig("plot_03_infection_percentage_by_country.png")
    plt.close()
    print("[OK] plot_03_infection_percentage_by_country.png")


# ============================================================
# 4. Efectividad de las vacunas
#    (Vaccine efficacy per vaccine brand?)
# ============================================================
def plot_vaccine_efficacy(conn):
    query = "SELECT brand, efficacy FROM vaccine;"
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[VACCINE] No hay datos en vaccine.")
        return

    plt.figure()
    df.plot(x="brand", y="efficacy", kind="bar", legend=False)
    plt.xlabel("Vaccine brand")
    plt.ylabel("Efficacy")
    plt.title("Vaccine efficacy by brand")
    plt.tight_layout()
    plt.savefig("plot_04_vaccine_efficacy_by_brand.png")
    plt.close()
    print("[OK] plot_04_vaccine_efficacy_by_brand.png")


# ============================================================
# 5. Tiempo total en lockdown por país
#    (Time of lockdown per country)
# ============================================================
def plot_lockdown_time_by_country(conn):
    query = """
    SELECT c.name,
           SUM(l.day_end - l.day_start + 1) AS total_lockdown_days
    FROM lockdown AS l
    JOIN country AS c ON c.country_id = l.country_id
    GROUP BY c.name;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[LOCKDOWN] No hay datos de lockdown.")
        return

    plt.figure()
    df.plot(x="name", y="total_lockdown_days", kind="bar", legend=False)
    plt.xlabel("Country")
    plt.ylabel("Total days in lockdown")
    plt.title("Total lockdown days per country")
    plt.tight_layout()
    plt.savefig("plot_05_lockdown_days_by_country.png")
    plt.close()
    print("[OK] plot_05_lockdown_days_by_country.png")


# ============================================================
# 6. Distribución de género de infectados y fallecidos
#    (Gender distribution of infected and deceased?)
# ============================================================
def plot_gender_distribution_infected_and_dead(conn):
    # Infectados (al menos una vez)
    infected_query = """
    SELECT p.sex, COUNT(*) AS count
    FROM patient AS p
    JOIN patient_state_per_day AS s ON p.patient_id = s.patient_id
    WHERE s.state = 'infected'
    GROUP BY p.sex;
    """
    df_inf = pd.read_sql_query(infected_query, conn)

    # Fallecidos (estado final = dead)
    dead_query = """
    SELECT p.sex, COUNT(*) AS count
    FROM patient AS p
    JOIN patient_result AS pr ON p.patient_id = pr.patient_id
    WHERE pr.final_state = 'dead'
    GROUP BY p.sex;
    """
    df_dead = pd.read_sql_query(dead_query, conn)

    if df_inf.empty and df_dead.empty:
        print("[GENDER] No hay datos de infectados/dead.")
        return

    sexes = sorted(set(df_inf["sex"]).union(df_dead["sex"]))
    df_plot = pd.DataFrame(index=sexes, columns=["infected", "dead"]).fillna(0)

    if not df_inf.empty:
        df_plot.loc[df_inf["sex"], "infected"] = df_inf["count"].values
    if not df_dead.empty:
        df_plot.loc[df_dead["sex"], "dead"] = df_dead["count"].values

    plt.figure()
    df_plot.plot(kind="bar")
    plt.xlabel("Sex")
    plt.ylabel("Number of patients")
    plt.title("Gender distribution of infected and deceased")
    plt.tight_layout()
    plt.savefig("plot_06_gender_distribution_infected_dead.png")
    plt.close()
    print("[OK] plot_06_gender_distribution_infected_dead.png")


# ============================================================
# 7. Correlación enfermedad respiratoria previa vs muertes
#    (Correlation between previous diseases and deaths)
# ============================================================
def plot_respiratory_disease_vs_death(conn):
    query = """
    SELECT p.respiratory_disease,
           pr.final_state
    FROM patient AS p
    JOIN patient_result AS pr ON p.patient_id = pr.patient_id;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[RESP] No hay datos suficientes.")
        return

    # 0 = no enfermedad, 1 = con enfermedad
    groups = df.groupby("respiratory_disease")
    stats = []
    for has_disease, sub in groups:
        total = len(sub)
        deaths = sum(sub["final_state"] == "dead")
        death_rate = deaths / total * 100 if total > 0 else 0
        stats.append({
            "respiratory_disease": "Yes" if has_disease == 1 else "No",
            "death_rate_pct": death_rate
        })

    df_stats = pd.DataFrame(stats)

    plt.figure()
    df_stats.plot(x="respiratory_disease", y="death_rate_pct", kind="bar", legend=False)
    plt.xlabel("Respiratory disease")
    plt.ylabel("Death rate (%)")
    plt.title("Death rate vs respiratory disease")
    plt.tight_layout()
    plt.savefig("plot_07_death_rate_respiratory_disease.png")
    plt.close()
    print("[OK] plot_07_death_rate_respiratory_disease.png")


# ============================================================
# 8. Relación entre presupuesto y recuperados
#    (Relationship between the budget and recovered patients)
# ============================================================
def plot_budget_vs_recovered(conn):
    # Usamos el último día para ver cuántos recuperados hay por país
    last_day_query = "SELECT MAX(day) AS max_day FROM metrics_per_country_day;"
    last_day = pd.read_sql_query(last_day_query, conn)["max_day"].iloc[0]

    query = """
    SELECT c.country_id,
           c.name,
           b.total_spend,
           m.recovered,
           (m.healthy + m.infected + m.recovered + m.dead) AS total_pop
    FROM country AS c
    JOIN budget AS b ON c.country_id = b.country_id
    JOIN metrics_per_country_day AS m ON c.country_id = m.country_id
    WHERE m.day = ?;
    """
    df = pd.read_sql_query(query, conn, params=(last_day,))

    if df.empty:
        print("[BUDGET] No hay datos para presupuesto vs recuperados.")
        return

    df["recovered_pct"] = df["recovered"] / df["total_pop"] * 100

    plt.figure()
    plt.scatter(df["total_spend"], df["recovered_pct"])
    for _, row in df.iterrows():
        plt.annotate(row["name"], (row["total_spend"], row["recovered_pct"]))
    plt.xlabel("Total spend (vaccines + medicines)")
    plt.ylabel("Recovered (%)")
    plt.title(f"Budget vs recovered rate (day {last_day})")
    plt.tight_layout()
    plt.savefig("plot_08_budget_vs_recovered.png")
    plt.close()
    print("[OK] plot_08_budget_vs_recovered.png")


# ============================================================
# 9. Relación entre apertura de fronteras y propagación
#    (Relationship between frontiers openness and virus spread)
# ============================================================
def plot_frontier_openness_vs_spread(conn):
    # 1) Apertura de fronteras aproximada por suma de intensidades de migración
    mig_query = """
    SELECT c.country_id,
           c.name,
           COALESCE(outgoing.out_intensity, 0) AS out_intensity,
           COALESCE(incoming.in_intensity, 0) AS in_intensity
    FROM country AS c
    LEFT JOIN (
        SELECT origin_country_id, SUM(intensity) AS out_intensity
        FROM migration_route
        GROUP BY origin_country_id
    ) AS outgoing ON c.country_id = outgoing.origin_country_id
    LEFT JOIN (
        SELECT dest_country_id, SUM(intensity) AS in_intensity
        FROM migration_route
        GROUP BY dest_country_id
    ) AS incoming ON c.country_id = incoming.dest_country_id;
    """
    mig_df = pd.read_sql_query(mig_query, conn)

    if mig_df.empty:
        print("[FRONTIERS] No hay datos en migration_route.")
        return

    mig_df["openness"] = mig_df["out_intensity"] + mig_df["in_intensity"]

    # 2) Propagación: porcentaje de infectados + recuperados (alguna vez infectados)
    last_day_query = "SELECT MAX(day) AS max_day FROM metrics_per_country_day;"
    last_day = pd.read_sql_query(last_day_query, conn)["max_day"].iloc[0]

    spread_query = """
    SELECT c.country_id,
           c.name,
           m.infected,
           m.recovered,
           (m.healthy + m.infected + m.recovered + m.dead) AS total_pop
    FROM country AS c
    JOIN metrics_per_country_day AS m ON c.country_id = m.country_id
    WHERE m.day = ?;
    """
    spread_df = pd.read_sql_query(spread_query, conn, params=(last_day,))

    df = pd.merge(mig_df, spread_df, on=["country_id", "name"], how="inner")
    if df.empty:
        print("[FRONTIERS] No hay datos suficientes para la relación apertura-propagación.")
        return

    df["spread_pct"] = (df["infected"] + df["recovered"]) / df["total_pop"] * 100

    plt.figure()
    plt.scatter(df["openness"], df["spread_pct"])
    for _, row in df.iterrows():
        plt.annotate(row["name"], (row["openness"], row["spread_pct"]))
    plt.xlabel("Frontier openness (migration intensity)")
    plt.ylabel("Spread (% ever infected)")
    plt.title(f"Frontier openness vs virus spread (day {last_day})")
    plt.tight_layout()
    plt.savefig("plot_09_frontier_openness_vs_spread.png")
    plt.close()
    print("[OK] plot_09_frontier_openness_vs_spread.png")


# ============================================================
# 10. Países y sus políticas (resumen simple)
#     (Countries and their policies)
# ============================================================
def table_countries_and_policies(conn):
    # Aquí no tenemos una tabla de políticas per se, pero podemos mostrar:
    # - país
    # - vacuna por defecto
    # - tratamiento principal
    # - probabilidad de uso de mascarilla
    query = """
    SELECT name, vaccine_brand, treatment_type, mask_prob
    FROM country;
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        print("[POLICIES] No hay datos en country.")
        return

    # Exportamos a CSV y también lo mostramos por pantalla
    df.to_csv("table_countries_policies.csv", index=False)
    print("[OK] table_countries_policies.csv generado.")
    print(df)


# ============================================================
# MAIN
# ============================================================
def main():
    conn = get_connection()

    try:
        plot_age_distribution_of_deceased(conn)
        plot_spending_by_country(conn)
        plot_infection_percentage_by_country(conn)
        plot_vaccine_efficacy(conn)
        plot_lockdown_time_by_country(conn)
        plot_gender_distribution_infected_and_dead(conn)
        plot_respiratory_disease_vs_death(conn)
        plot_budget_vs_recovered(conn)
        plot_frontier_openness_vs_spread(conn)
        table_countries_and_policies(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
