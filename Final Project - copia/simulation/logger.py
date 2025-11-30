#LOGGING DATA INTO THE DATABASE

import sqlite3
import threading
from pathlib import Path

class SQLiteLogger:
    def __init__(self, db_path="simulation.sqlite"):
        #Path of the SQlite database where all simulation data will be saved
        self.db_path = Path(db_path)
        #Connect to the database
        #check_same_thread=False allows using it
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        #Basic sqlite performance settings.
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")

        self._create_tables()

        #Buffers para batch inserts
        #Batch inserts are much faster than logging each event separately
        self.daily_states = []
        self._migration_counts = {}

        #Tracks special events for patients
        self._first_infected = {}
        self._recovered_day = {}
        self._death_day = {}

    #Table creation
    def _create_tables(self):
        cur = self.conn.cursor()

        #Table country
        cur.execute("""
        CREATE TABLE IF NOT EXISTS country (
            country_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            population      INTEGER NOT NULL,
            vaccine_brand   TEXT NOT NULL,
            treatment_type  TEXT NOT NULL,
            mask_prob       REAL NOT NULL
        );
        """)

        #Table patient
        cur.execute("""
        CREATE TABLE IF NOT EXISTS patient (
            patient_id         INTEGER PRIMARY KEY,
            country_id         INTEGER NOT NULL REFERENCES country(country_id),
            sex                TEXT NOT NULL,
            age                INTEGER NOT NULL,
            respiratory_disease INTEGER NOT NULL,
            vaccinated         INTEGER NOT NULL,
            mask               INTEGER NOT NULL,
            superspreader      INTEGER NOT NULL
        );
        """)

        #Table vaccine
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vaccine (
            brand     TEXT PRIMARY KEY,
            efficacy  REAL NOT NULL,
            unit_cost REAL NOT NULL
        );
        """)

        #Table treatment
        cur.execute("""
        CREATE TABLE IF NOT EXISTS treatment (
            brand     TEXT PRIMARY KEY,
            efficacy  REAL NOT NULL,
            unit_cost REAL NOT NULL
        );
        """)

        #Table budget
        cur.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            country_id          INTEGER PRIMARY KEY REFERENCES country(country_id),
            vaccine_units       INTEGER NOT NULL,
            medicine_units      INTEGER NOT NULL,
            vaccine_unit_cost   REAL NOT NULL,
            medicine_unit_cost  REAL NOT NULL,
            total_vaccine_spend REAL GENERATED ALWAYS AS (vaccine_units * vaccine_unit_cost) STORED,
            total_medicine_spend REAL GENERATED ALWAYS AS (medicine_units * medicine_unit_cost) STORED,
            total_spend         REAL GENERATED ALWAYS AS (total_vaccine_spend + total_medicine_spend) STORED
        );
        """)

        #Table lockdowns
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lockdown (
            lockdown_id INTEGER PRIMARY KEY,
            country_id  INTEGER NOT NULL REFERENCES country(country_id),
            day_start   INTEGER NOT NULL,
            day_end     INTEGER NOT NULL
        );
        """)

        #Table daily status
        cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_state_per_day (
            patient_id INTEGER NOT NULL REFERENCES patient(patient_id),
            day        INTEGER NOT NULL,
            state      TEXT NOT NULL CHECK (state IN ('healthy','infected','recovered','dead')),
            PRIMARY KEY (patient_id, day)
        );
        """)

        #Vaccine usage
        cur.execute("""
               CREATE TABLE IF NOT EXISTS vaccine_usage (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   country_id INTEGER NOT NULL,
                   brand TEXT NOT NULL,
                   units INTEGER NOT NULL,
                   FOREIGN KEY(country_id) REFERENCES country(country_id)
               );
               """)

        #Final results per patient
        cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_result (
            patient_id        INTEGER PRIMARY KEY REFERENCES patient(patient_id),
            first_infected_day INTEGER,
            recovered_day     INTEGER,
            death_day         INTEGER,
            final_state       TEXT NOT NULL CHECK (final_state IN ('healthy','infected','recovered','dead'))
        );
        """)

        #Daily country metrics
        cur.execute("""
        CREATE TABLE IF NOT EXISTS metrics_per_country_day (
            country_id INTEGER NOT NULL REFERENCES country(country_id),
            day        INTEGER NOT NULL,
            healthy    INTEGER NOT NULL,
            infected   INTEGER NOT NULL,
            recovered  INTEGER NOT NULL,
            dead       INTEGER NOT NULL,
            PRIMARY KEY (country_id, day)
        );
        """)

        #Travel
        cur.execute("""
        CREATE TABLE IF NOT EXISTS migration_route (
            origin_country_id INTEGER NOT NULL REFERENCES country(country_id),
            dest_country_id   INTEGER NOT NULL REFERENCES country(country_id),
            intensity         REAL NOT NULL,
            PRIMARY KEY (origin_country_id, dest_country_id)
        );
        """)



        self.conn.commit()

    #Catalog
    #Insert or update vaccines in the database.
    def upsert_vaccine(self, brand, efficacy, unit_cost):
        with self._lock:
            self.conn.execute("""
            INSERT INTO vaccine (brand, efficacy, unit_cost)
            VALUES (?, ?, ?)
            ON CONFLICT(brand) DO UPDATE SET
                efficacy=excluded.efficacy,
                unit_cost=excluded.unit_cost;
            """, (brand, efficacy, unit_cost))
            self.conn.commit()

    # Insert or update treatments.
    def upsert_treatment(self, brand, efficacy, unit_cost):
        with self._lock:
            self.conn.execute("""
            INSERT INTO treatment (brand, efficacy, unit_cost)
            VALUES (?, ?, ?)
            ON CONFLICT(brand) DO UPDATE SET
                efficacy=excluded.efficacy,
                unit_cost=excluded.unit_cost;
            """, (brand, efficacy, unit_cost))
            self.conn.commit()

    #Country + patients + budget
    def insert_country(self, country):
        #Save or update a country's main information.
        #Returns the database ID needed for linking patients later.
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("""
            INSERT INTO country (name, population, vaccine_brand, treatment_type, mask_prob)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                population     = excluded.population,
                vaccine_brand  = excluded.vaccine_brand,
                treatment_type = excluded.treatment_type,
                mask_prob      = excluded.mask_prob;
            """, (
                country.name,
                len(country.patients),
                country.vaccine,
                country.treatment,
                country.mask_prob,
            ))
            self.conn.commit()

            cur.execute("SELECT country_id FROM country WHERE name=?;", (country.name,))
            return cur.fetchone()[0]

    def insert_lockdowns(self, country_id, lockdown_days):
    #Store lockdown periods for a given country.
        with self._lock:
            cur = self.conn.cursor()
            for s, e in lockdown_days:
                cur.execute("""
                INSERT INTO lockdown (country_id, day_start, day_end)
                VALUES (?, ?, ?);
                """, (country_id, s, e))
            self.conn.commit()

    def insert_budget(self, country_id, vaccine_units, medicine_units,
                      vaccine_unit_cost, medicine_unit_cost):
    #Store or update budget data for vaccines & medicines.

        with self._lock:
            self.conn.execute("""
            INSERT INTO budget (country_id, vaccine_units, medicine_units,
                                vaccine_unit_cost, medicine_unit_cost)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(country_id) DO UPDATE SET
                vaccine_units      = excluded.vaccine_units,
                medicine_units     = excluded.medicine_units,
                vaccine_unit_cost  = excluded.vaccine_unit_cost,
                medicine_unit_cost = excluded.medicine_unit_cost;
            """, (
                country_id, vaccine_units, medicine_units,
                vaccine_unit_cost, medicine_unit_cost
            ))
            self.conn.commit()

    def insert_patient(self, country_id, p):
        #Insert a single patient with all their fixed attributes.
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("""
            INSERT INTO patient (country_id, sex, age,
                                 respiratory_disease, vaccinated, mask, superspreader)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                country_id,
                p.sex,
                p.age,
                1 if p.respiratory_disease else 0,
                1 if p.vaccinated else 0,
                1 if p.mask else 0,
                1 if p.is_superspreader else 0,
            ))
            pid = cur.lastrowid
            self.conn.commit()
            return pid

    #Daily logging
    def log_patient_state(self, patient, day):
        #Writing to SQLite one-by-one was very slow.
        #Batch insertion is faster.
        self.daily_states.append((patient.db_id, day, patient.state))

        pid = patient.db_id
        state = patient.state

        #Record special events
        if state == "infected":
            if pid not in self._first_infected:
                self._first_infected[pid] = day
        elif state == "recovered":
            self._recovered_day[pid] = day
        elif state == "dead":
            self._death_day[pid] = day

    def flush_daily_states(self):
        #Write accumulated patient states to the DB
        if not self.daily_states:
            return
        with self._lock:
            cur = self.conn.cursor()
            cur.executemany("""
                INSERT INTO patient_state_per_day (patient_id, day, state)
                VALUES (?, ?, ?)
            """, self.daily_states)
            self.conn.commit()
        self.daily_states = []

    #Country daily metrics, will be later used for plots
    def log_metrics(self, country_id, day, healthy, infected, recovered, dead):
        with self._lock:
            self.conn.execute("""
            INSERT INTO metrics_per_country_day (country_id, day, healthy, infected, recovered, dead)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(country_id, day) DO UPDATE SET
                healthy=excluded.healthy,
                infected=excluded.infected,
                recovered=excluded.recovered,
                dead=excluded.dead;
            """, (country_id, day, healthy, infected, recovered, dead))
            self.conn.commit()

    #Migration
    def log_travel(self, origin_country_id, dest_country_id):
        #Count every trip in memory
        key = (origin_country_id, dest_country_id)
        self._migration_counts[key] = self._migration_counts.get(key, 0) + 1

    def finalize_migration_routes(self, populations_by_id):
        #Convert total travel counts into "intensity" (count / population)
        #Finally store them to the DB
        with self._lock:
            cur = self.conn.cursor()
            for (origin_id, dest_id), count in self._migration_counts.items():
                pop = populations_by_id.get(origin_id, 1)
                intensity = count / pop
                cur.execute("""
                INSERT INTO migration_route (origin_country_id, dest_country_id, intensity)
                VALUES (?, ?, ?)
                ON CONFLICT(origin_country_id, dest_country_id) DO UPDATE SET
                    intensity=excluded.intensity;
                """, (origin_id, dest_id, intensity))
            self.conn.commit()

    #Stores the vaccines usage
    def insert_vaccine_usage(self, country_id, vaccine_units_dict):
        with self.conn:
            for brand, units in vaccine_units_dict.items():
                if units > 0:
                    self.conn.execute(
                        "INSERT INTO vaccine_usage (country_id, brand, units) VALUES (?, ?, ?)",
                        (country_id, brand, units),
                    )

    #Final results per patient
    def finalize_patient_results(self, patients):
        with self._lock:
            cur = self.conn.cursor()
            for p in patients:
                pid = p.db_id
                final_state = p.state
                cur.execute("""
                INSERT INTO patient_result (patient_id, first_infected_day,
                                            recovered_day, death_day, final_state)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    first_infected_day=excluded.first_infected_day,
                    recovered_day=excluded.recovered_day,
                    death_day=excluded.death_day,
                    final_state=excluded.final_state;
                """, (
                    pid,
                    self._first_infected.get(pid),
                    self._recovered_day.get(pid),
                    self._death_day.get(pid),
                    final_state,
                ))
            self.conn.commit()
