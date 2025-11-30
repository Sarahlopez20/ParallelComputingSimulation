#TRAVELLING
from .events import EventBus

class MigrationRouter:
    def __init__(self, countries, event_bus: EventBus, logger=None):
        #List of all countries in the simulation
        self.countries = countries

        #EventBus to notify other parts of the system when something happens
        self.bus = event_bus

        #Logger to record travel data in the database
        self.logger = logger

    def try_travel(self, patient, policy, day) -> bool:
        import random

        #Dead patients can never travel
        if patient.state == "dead":
            return False

        #Check if this patient is allowed to travel today based on the policy
        #If the random chance is above the allowed probability he/she can not travel
        if random.random() > policy.travel_probability(patient, day):
            return False

        #Pick a destination country according to the migration policy.
        destination = policy.pick_destination(patient, self.countries)

        #If no destination is chosen or destination is the same as origin then no travel
        if destination is None or destination is patient.country:
            return False

        origin = patient.country

        #Remove the patient from the origin country
        with origin.lock:
            #Double-check the patient is still there (thread safety)
            if patient not in origin.patients:
                return False
            origin.patients.remove(patient)
            origin.travellers_out_today += 1

        #Add the patient to the destination country
        with destination.lock:
            destination.patients.append(patient)
            destination.travellers_in_today += 1

        #Update the patient's current country
        patient.country = destination

        #Log the travel in the database if the logger is available.
        if (self.logger is not None and
            origin.db_id is not None and
            destination.db_id is not None):
            self.logger.log_travel(origin.db_id, destination.db_id)

        return True