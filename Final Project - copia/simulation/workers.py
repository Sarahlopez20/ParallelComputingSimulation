#THREADPOOL FOR BATCHES
"""
These are the worker utilities for parallel processing of patients.

This module is used by the Simulation engine together with a ThreadPoolExecutor.

Parallelism model:
 - The simulation submits many of these batch tasks (10 patients per task).
 - Each worker thread calls this function with its own list of patients.
 - The shared states (patients list, budgets, hospital capacity, traveller counts)
    are protected by locks inside Country and MigrationRouter.
"""

from .disease import infection_step

#Processes a batch of patients for a single simulation day. It applies
#the infection dynamics to each patient and the travel decisions.
def process_patient_batch(patients, simulation, country, day):

    #Current travel policy for this country
    policy = simulation._policy_obj_by_country.get(country.name)
    router = simulation.router

    #Infection dynamics
    for p in patients:
        try:
            #Step 1: Apply disease progression and possible new infections
            infection_step(p, country, day)

            #Step 2: Travel decision
            if policy is not None and p.state != "dead":
                origin = p.country
                travelled = router.try_travel(p, policy, day)

                if travelled:
                    destination = p.country

                    #Counts one departure from the origin
                    with origin.lock:
                        origin.travellers_out_today += 1

                    #Counts one arrival in the destination
                    with destination.lock:
                        destination.travellers_in_today += 1

        #To avoid one bad patient crashing a whole worker
        except Exception as exc:
            print(
                f"[WARN] Exception processing patient {getattr(p, 'db_id', None)} "
                f"on day {day} in {country.name}: {exc}"
            )