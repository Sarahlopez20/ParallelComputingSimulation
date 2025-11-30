#CORE SIMULATION ENGINE
"""
This module coordinates the following processes:
- the daily evolution of the pandemic (infection, recovery, death),
- travel between countries using travel policies,
- adaptive policies reacting to infection rates,
- vaccination campaigns and limited health system resources,
- the parallel execution of patients using a ThreadPoolExecutor
"""
import random
from concurrent.futures import ThreadPoolExecutor, wait

from .policies import day_policy_for, adaptive_policy_for
from .events import EventBus, PolicyReporterObserver
from .migration import MigrationRouter
from .workers import process_patient_batch
from .models import Country
from .logger import SQLiteLogger
from .config import (
    VACCINE_COST,
    VACCINATION_CAMPAIGN_DAY,
    TREATMENT_COST,
    vaccine_effectiveness,
    treatment_effectiveness,
)

#This is a simple iterator for simulation days.
#Helps keep the daily loop explicit.
class SimulationDays:
    def __init__(self, start=1, end=30):
        self.current = start
        self.end = end

    def __iter__(self):
        return self

    def __next__(self):
        if self.current > self.end:
            raise StopIteration
        d = self.current
        self.current += 1
        return d

#Coordinates countries, patients, workers and logging.
class Simulation:
    def __init__(self, countries, max_workers=32, batch_size=10, logger=None):
        self.countries = countries
        self.all_patients = [p for c in countries for p in c.patients]
        self.total_travel = 0

        #Parallel execution settings
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self.logger = logger

        #Event Bus and policy observer
        self.bus = EventBus()
        self.policy_reporter = PolicyReporterObserver()
        self.bus.subscribe(self.policy_reporter)

        #Migration Router to handle travel between countries
        self.router = MigrationRouter(countries, self.bus, logger=self.logger)

        #Current policy per country
        self._policy_obj_by_country = {c.name: None for c in countries}

    #This seeds the virus only in Italy
    def seed_virus(self):
        from .config import INITIAL_INFECTED_FRAC, INFECTIOUS_PERIOD_RANGE
        from .disease import allocate_treatment_if_budget

        #Resets all patients to a clean initial state when we run the simulation
        for c in self.countries:
            for p in c.patients:
                p.reset()

        #Infects a fraction of the patients in Italy
        italy = next((c for c in self.countries if c.name == "Italy"), None)
        if not italy:
            raise ValueError("Italy should exist to seed the virus")

        initial_k = int(len(italy.patients) * INITIAL_INFECTED_FRAC)
        if initial_k <= 0:
            print("Warning: initial_k <= 0, no initial infection in Italy.")
            return

        for p in random.sample(italy.patients, k=initial_k):
            p.state = "infected"
            p.infectious_period = random.randint(*INFECTIOUS_PERIOD_RANGE)
            allocate_treatment_if_budget(italy, p)

        infected = sum(1 for p in italy.patients if p.state == "infected")
        print(f"\nVIRUS SEEDED IN ITALY ONLY. Number of initial infected: {infected}\n")

    #Daily Vaccination Campaign
    def run_vaccination_campaign(self, country, day):

        #Runs the campaign only after the starting day is reached
        if day < VACCINATION_CAMPAIGN_DAY:
            return

        #If no vaccines available in this country
        if not country.vaccines:
            return

        #The main vaccine is used
        main_vaccine = country.vaccine
        unit_cost = VACCINE_COST.get(main_vaccine, 0)
        if unit_cost <= 0:
            return

        with country.lock:
            #Maximum vaccines countries can pay
            max_by_budget = int(country.budget_remaining // unit_cost)
            if max_by_budget <= 0:
                return

            #Daily capacity constraint
            remaining_capacity = country.daily_vaccination_capacity
            if remaining_capacity <= 0:
                return

            max_to_vaccinate = min(max_by_budget, remaining_capacity)

            #We select the candidates. Those alive and not yet vaccinated
            candidates = [
                p for p in country.patients
                if (p.state != "dead" and not p.vaccinated)
            ]

            if not candidates:
                return

            #Priorities:
            #1) Patients with a respiratory disease
            #2) Older patients

            def risk_key(p):
                high_risk = 1 if p.respiratory_disease or p.age >= 65 else 0
                return (high_risk, p.age)

            candidates.sort(key=risk_key, reverse=True)
            to_vaccinate = candidates[:max_to_vaccinate]

            for p in to_vaccinate:
                #In case, the budget runs out in the middle of the day
                if country.budget_remaining < unit_cost:
                    break
                if p.vaccinated:
                    continue

                p.vaccinated = True
                p.vaccine_type = main_vaccine
                country.budget_remaining -= unit_cost
                country.budget_spent_vaccines += unit_cost
                country.vaccinated_today += 1
                country.vaccine_units_given[main_vaccine] += 1

    #Main simulation loop
    def run(self, max_days=30):
        self.seed_virus()

        for day in SimulationDays(1, max_days):
            from .config import VARIANT_DAY
            print(f"\n================= DAY {day} =================")
            if day == VARIANT_DAY:
                print("🧬 ⚠️ NEW VARIANT DETECTED: more contagious and vaccines less effective.")

            #Step 1: Reset counters and update transmission rates
            for country in self.countries:
                country.treatments_given_today = 0
                country.travellers_in_today = 0
                country.travellers_out_today = 0
                country.vaccinated_today = 0
                country.update_transmission(day)

                #Runs the daily vaccination campaign
                self.run_vaccination_campaign(country, day)

            #Step 2: Compute infection rates per country
            infection_rates = {}
            for country in self.countries:
                with country.lock:
                    total = len(country.patients)
                    infected = sum(1 for p in country.patients if p.state == "infected")
                infection_rates[country.name] = infected / total if total > 0 else 0.0

            #Step 3: Choose the travel policy for each country
            print("\n🚦 Travel policies:")
            for country in self.countries:
                #Belgium and UK use adaptive policies
                if country.name in ("Belgium", "UK") and day > 1:
                    policy = adaptive_policy_for(country, day, infection_rates[country.name])
                else:
                    policy = day_policy_for(country.name, day)

                country.current_policy = policy
                self._policy_obj_by_country[country.name] = policy

                #Notify the observers and print policy changes
                self.bus.publish(
                    "policy_change",
                    country=country,
                    day=day,
                    new_policy_name=policy.name()
                )

            #Step 4: Submit batch tasks to the threadpool
            futures = []
            for country in self.countries:
                with country.lock:
                    alive = [p for p in country.patients if p.state != "dead"]

                for i in range(0, len(alive), self.batch_size):
                    batch = alive[i:i + self.batch_size]
                    futures.append(
                        self.executor.submit(process_patient_batch,
                                             batch,
                                             self,
                                             country,
                                             day)
                                            )
            #Waits for all workers to finish for this day
            wait(futures)

            #Step 5: Log patient states
            if self.logger is not None:
                for c in self.countries:
                    with c.lock:
                        for p in c.patients:
                            self.logger.log_patient_state(p, day)

            #Step 6: Print Travel Summary
            print("\n✈️  Daily Travels:")
            for country in self.countries:
                print(
                    f"   - {country.name:8} | out: {country.travellers_out_today:4} | in: {country.travellers_in_today:4}"
                )

            #Step 7: Print Vaccination Summary
            print("\n💉 Daily Vaccination:")
            for country in self.countries:
                print(f"   - {country.name:8} | newly vaccinated: {country.vaccinated_today:4}")

            #Step 8: Print Epidemiological Summary
            print("\n📊 Epidemiological State per Country:")
            for country in self.countries:
                nat = country.name
                h = sum(1 for p in self.all_patients if p.nationality == nat and p.state == "healthy")
                f = sum(1 for p in self.all_patients if p.nationality == nat and p.state == "infected")
                r = sum(1 for p in self.all_patients if p.nationality == nat and p.state == "recovered")
                d = sum(1 for p in self.all_patients if p.nationality == nat and p.state == "dead")
                print(
                    f"   - {nat:8} | 😷 Healthy: {h:4} | 🤒 Infected: {f:4} | ✅ Rec: {r:4} | ☠️ Dead: {d:4}"
                )

                #If available, logs aggreagate metrics per country
                if self.logger is not None and country.db_id is not None:
                    self.logger.log_metrics(country.db_id, day, h, f, r, d)

        #After all days, finalises logger and prints the global summary
        if self.logger is not None:
            self.logger.finalize_patient_results(self.all_patients)
            populations_by_id = {c.db_id: len(c.patients) for c in self.countries}
            self.logger.finalize_migration_routes(populations_by_id)

        self.final_summary()
        self.executor.shutdown(wait=True)

    #Final Summary
    def final_summary(self):
        total_h = total_i = total_r = total_d = 0
        for p in self.all_patients:
            if p.state == "healthy":
                total_h += 1
            elif p.state == "infected":
                total_i += 1
            elif p.state == "recovered":
                total_r += 1
            elif p.state == "dead":
                total_d += 1
        print("\n=========== FINAL RESULT ===========")
        print(f"Total Healthy:   {total_h}")
        print(f"Total Infected:  {total_i}")
        print(f"Total Recovered: {total_r}")
        print(f"Total Dead:      {total_d}")
        print("=======================================")

#Creates the base configuration of the countries
def build_default_world(db_path="data/simulation.sqlite"):
    countries = [
        Country("Germany", ["A", "B"], ["T1", "T2"], 0.9, [(8, 17),(23,28)]),
        Country("Italy",   ["C"],       ["T1"],       0.8, [(5, 15)]),
        Country("France",  ["A","B"],       ["T2"],       0.6, [(10, 18), (22, 26)]),
        Country("Spain",   ["B", "C"],  ["T2"],       0.7, [(10, 22)]),
        Country("Sweden",  ["C"],  ["T2"],       0.2, []),
        Country("Belgium", ["B", "C"],  ["T2"],       0.8, [(1, 10)]),
        Country("UK",      ["A", "B"],  ["T1", "T2"], 0.9, [(12, 20)]),
    ]

    #Initialises SQLiteLogger
    logger = SQLiteLogger(db_path=db_path)

    #Catalogue pf Vaccines and Treatments
    for brand, eff in vaccine_effectiveness.items():
        logger.upsert_vaccine(brand, eff, VACCINE_COST[brand])
    for brand, eff in treatment_effectiveness.items():
        logger.upsert_treatment(brand, eff, TREATMENT_COST)

    #Insert countries, lockdowns, budgets and patients
    for c in countries:
        cid = logger.insert_country(c)
        c.db_id = cid
        logger.insert_lockdowns(cid, c.lockdown_days)

        #Stores the number of vaccine and treatment units spent
        total_vaccine_units = sum(c.vaccine_units_given.values())
        medicine_units = c.budget_spent_treatments

        logger.insert_budget(
            cid,
            total_vaccine_units,
            medicine_units,
            VACCINE_COST.get(c.vaccine, 0.0),
            TREATMENT_COST,
        )

        logger.insert_vaccine_usage(cid, c.vaccine_units_given)

        #Inserts patients into the database
        for p in c.patients:
            pid = logger.insert_patient(cid, p)
            p.db_id = pid

    sim = Simulation(countries, max_workers=32, batch_size=10, logger=logger)
    sim.logger = logger
    return sim