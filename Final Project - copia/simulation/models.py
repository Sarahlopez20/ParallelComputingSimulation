#PATIENT AND COUNTRY CLASSES

import random
import threading
from .config import (
    TRANSMISSION_BASE,
    VACCINE_COST,
    VARIANT_DAY,
    VARIANT_TRANSMISSION_MULTIPLIER
)

"""
The Class Patient represents one individual in the simulation. It contains the 
demographic and clinical attributes of a person:
    
Patients are intentionally not threads because it would mean containing thousand 
of threads. Instead, the simulation uses a ThreadPoolExecutor that processes patients 
in batches (10 patients per worker thread). Each batch worker
applies infection dynamics and travel decisions to a group of patients.
"""

class Patient:
    def __init__(self, nationality, country):
        #ID for the database, filled in by the logger
        self.db_id = None

        #Fixed Attributes
        self.country = country
        self.nationality = nationality
        self.sex = random.choice(["M", "F"])
        self.age = random.randint(1, 90)
        self.mask = random.random() < country.mask_prob
        self.respiratory_disease = random.random() < 0.12
        self.is_superspreader = random.random() < 0.05

       #Disease State
        self.state = "healthy"
        self.days_infected = 0
        self.infectious_period = None
        self.hospitalized = False

        #Vaccination and Treatment
        self.vaccinated = False
        self.vaccine_type = None
        self.has_treatment = False
        self.treatment_type = None

    #Reset() ensures that every simulation starts from day 0 clean,
    #returning the patients to an initial state.
    def reset(self):
        self.state = "healthy"
        self.days_infected = 0
        self.infectious_period = None
        self.has_treatment = False
        self.treatment_type = None
        self.hospitalized = False

    #Computes the baseline death probability given the attributes of the patient
    def death_probability(self):
        base = 0.02
        if self.age > 60:
            base *= 3
        elif self.age > 40:
            base *= 2
        if self.sex == "M":
            base *= 1.15
        if self.respiratory_disease:
            base *= 2
        return base

#This class is the container for the patients, policies and health system resources
class Country:
    def __init__(self, name, vaccines, treatments, mask_prob, lockdown_days):
        self.db_id = None
        self.name = name

        #Available vaccines and treatments in this country
        self.vaccines   = list(vaccines) if isinstance(vaccines, (list, tuple, set)) else [vaccines]
        self.treatments = list(treatments) if isinstance(treatments, (list, tuple, set)) else [treatments]
        self.vaccine   = self.vaccines[0]
        self.treatment = self.treatments[0]

        #Fixed attributes
        self.mask_prob = mask_prob
        self.lockdown_days = lockdown_days

        #Population
        self.patients = [Patient(name, self) for _ in range(500)]
        self.base_transmission = TRANSMISSION_BASE

        """
        Reentrant Lock: It prevents deadlocks when the same thread re-enters a locked section
        In our simulation, it is important because there are methods that use a lock which call
        another method that also use the same lock.
        """
        self.lock = threading.RLock()

        #Economic model
        budget_map = {
            "Germany": 1500,
            "France": 1000,
            "Italy": 850,
            "Spain": 700,
            "Sweden": 1000,
            "Belgium": 900,
            "UK": 1300,
        }
        self.budget_total = budget_map.get(name, 800)
        self.budget_remaining = self.budget_total
        self.budget_spent_vaccines = 0
        self.budget_spent_treatments = 0

        #Health system capacity
        self.hospital_capacity = max(50, self.budget_total // 4)
        self.current_hospitalized = 0

        #Treatment constraints
        self.max_daily_treatments = max(20, self.budget_total // 8)
        self.treatments_given_today = 0

        #Vaccination constraints
        self.daily_vaccination_capacity = max(10, self.budget_total // 15)
        self.vaccinated_today = 0

        #Travel counters
        self.travellers_in_today = 0
        self.travellers_out_today = 0

        #Travel policy
        self.current_policy = None

        #Half of the population gets vaccinated if possible
        self.vaccine_units_given = {code: 0 for code in VACCINE_COST.keys()}
        self._initial_vaccination()

    #Apply an initial vaccination campaign before the simulation starts
    def _initial_vaccination(self):
        if not self.vaccines or self.vaccines is None:
            return

        for p in self.patients:
            if random.random() < 0.5 and self.budget_remaining > 0:
                affordable = [
                    v for v in self.vaccines
                    if self.budget_remaining >= VACCINE_COST[v]]
                if not affordable:
                    break
                vtype = random.choice(affordable)
                with self.lock:
                    if self.budget_remaining < VACCINE_COST[vtype]:
                        continue
                    p.vaccinated = True
                    p.vaccine_type = vtype
                    self.budget_remaining -= VACCINE_COST[vtype]
                    self.budget_spent_vaccines += VACCINE_COST[vtype]

                    #Counts units per brand
                    self.vaccine_units_given[vtype] += 1

    #Updates the base_transmission to the new variant
    def update_transmission(self, day:int):
        base = TRANSMISSION_BASE
        if day >= VARIANT_DAY:
            base *= VARIANT_TRANSMISSION_MULTIPLIER
        self.base_transmission = base


