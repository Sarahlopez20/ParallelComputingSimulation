#TRAVEL POLICIES THAT CAN BE APPLIED BY THE COUNTRIES

"""
This module implements the Strategy Pattern for travel decisions.
Each concrete travel policy shares the same interface, so the simulation
can dynamically switch behaviors per country and per day without modifying
the core simulation logic. This keeps the code modular and thread-safe.
"""

import random
from .config import BASE_TRAVEL_PROB

"""
This is the Strategy Base. 
Each policy defines:
    - travel_probability - probability that a given patient travels on a given day.
    - pick_destination - where they travel to if they do.
"""
class TravelPolicy:
    def travel_probability(self, patient, day) -> float: return 0.0
    def pick_destination(self, patient, countries): return None
    def name(self) -> str: return self.__class__.__name__

#Borders closed, no travelling
class NoTravel(TravelPolicy):
    def travel_probability(self, patient, day): return 0.0

#Only 10% of the base travel probability
class TenPercent(TravelPolicy):
    def travel_probability(self, patient, day): return BASE_TRAVEL_PROB * 0.10
    def pick_destination(self, patient, countries):
        choices = [c for c in countries if c is not patient.country]
        return random.choice(choices) if choices else None

#Full base travel probability
class FreeTravel(TravelPolicy):
    def travel_probability(self, patient, day): return BASE_TRAVEL_PROB
    def pick_destination(self, patient, countries):
        choices = [c for c in countries if c is not patient.country]
        return random.choice(choices) if choices else None

#Time based policy schedule
"""
This is the fixed time-based policy schedule for the non-adaptive countries.

    - Days 2–9: Italy and Sweden very open, others at low mobility.
    - Days 10–20: Germany becomes strict, others at low mobility.
    - Days 21–30: Sweden stays very open, others at low mobility.

This baseline can be overridden by adaptive_policy_for for some countries.
"""

def day_policy_for(country_name: str, day: int) -> TravelPolicy:
    if day == 1:
        return NoTravel()

    if 2 <= day <= 9:
        return FreeTravel() if country_name in ("Italy", "Sweden") else TenPercent()

    if 10 <= day <= 20:
        return NoTravel() if country_name == "Germany" else TenPercent()

    return FreeTravel() if country_name == "Sweden" else TenPercent()

#Adaptive travel policy based on current infection rate
def adaptive_policy_for(country, day, infection_rate: float) -> TravelPolicy:

    #First period without adaptivity
    if day <= 3:
        return day_policy_for(country.name, day)

    # Belgium: very conservative
    if country.name == "Belgium":

        #Very high infection - Strong closure
        if infection_rate > 0.20:
            return NoTravel()

        #Moderate infection - Restricted Travel
        elif infection_rate > 0.05:
            return TenPercent()

        #Low infection - Normal Travel
        else:
            return FreeTravel()

    # UK: less conservative
    if country.name == "UK":
        if infection_rate > 0.30:
            return NoTravel()
        elif infection_rate > 0.10:
            return TenPercent()
        else:
            return FreeTravel()

    return day_policy_for(country.name, day)
