#LOGIC FOR DISEASES AND HOSPITAL
import random
from .config import (
    MASK_EFFECTIVENESS,
    INFECTIOUS_PERIOD_RANGE,
    DAILY_DEATH_MULTIPLIER,
    VARIANT_DAY,
    VARIANT_VACCINE_EFFECTIVENESS_DROP,
    TREATMENT_COST,
    LOCKDOWN_CONTACT_FACTOR,
    CONTACTS_RANGE,
    SUPERSPREADER_MULTIPLIER,
    treatment_effectiveness,
    vaccine_effectiveness,
)

def allocate_treatment_if_budget(country, patient):
    #Assign treatment or hospitalization to a patient if the country has resources

    with country.lock:
        patient.hospitalized = False

        #No treatment available
        if not country.treatments:
            patient.has_treatment = False
            patient.treatment_type = None
            return

        #Identifies high risk patients
        high_risk = (patient.age >= 65) or patient.respiratory_disease

        #Identify which countries can afford treatment today: Two conditions
        can_treat_today = (
            country.budget_remaining >= TREATMENT_COST
            and country.treatments_given_today < country.max_daily_treatments
        )

        if can_treat_today:
            #Country avoids overspending unless patient is high-risk
            safety_threshold = 0.3 * country.budget_total
            if high_risk or country.budget_remaining > safety_threshold:
                patient.has_treatment = True
                patient.treatment_type = random.choice(country.treatments)
                country.budget_remaining -= TREATMENT_COST
                country.budget_spent_treatments += TREATMENT_COST
                country.treatments_given_today += 1
            else:
                patient.has_treatment = False
                patient.treatment_type = None
        else:
            patient.has_treatment = False
            patient.treatment_type = None

        #High risk patients may be hospitalized if capacity allows
        if high_risk and country.current_hospitalized < country.hospital_capacity:
            patient.hospitalized = True
            country.current_hospitalized += 1


def infection_step(patient, country, day):
    #One day of disease progression for a single patient

    p = patient

    #Only infected patients continue through the infection process
    if p.state in ("healthy", "recovered", "dead"):
        return

    high_risk = (p.age >= 65) or p.respiratory_disease

    #Assign an infectious period the first time
    if p.infectious_period is None:
        p.infectious_period = random.randint(*INFECTIOUS_PERIOD_RANGE)

    #List of healthy people who could be infected
    with country.lock:
        healthy_people = [x for x in country.patients if x.state == "healthy"]

    #Infection spread phase (before recovery/death)
    if p.days_infected < p.infectious_period:
        cmin, cmax = CONTACTS_RANGE
        contacts_count = random.randint(cmin, cmax)

        #Lockdown reduces contacts
        in_lockdown = any(s <= day <= e for (s, e) in country.lockdown_days)
        if in_lockdown:
            contacts_count = max(1, int(contacts_count * LOCKDOWN_CONTACT_FACTOR))

        #Superspreaders multiply the number of contacts
        if p.is_superspreader:
            contacts_count *= SUPERSPREADER_MULTIPLIER

        #Choose people contacted today
        with country.lock:
            contacts = random.sample(
                healthy_people,
                #This ensures we never try to select more healthy people than actually exist
                k=min(len(healthy_people), contacts_count)
            ) if healthy_people else []

        #Attempt to infect each contact, calculates probability
        for target in contacts:
            prob = country.base_transmission

            #Mask effect
            if target.mask:
                prob *= (1 - MASK_EFFECTIVENESS)
            if p.mask:
                prob *= (1 - MASK_EFFECTIVENESS)

            #Vaccine effect
            if target.vaccinated:
                vtype = target.vaccine_type or country.vaccine
                eff = vaccine_effectiveness[vtype]

                #The new variant reduces vaccine effectiveness
                if day >= VARIANT_DAY:
                    eff = max(0.0, eff - VARIANT_VACCINE_EFFECTIVENESS_DROP)
                prob *= (1 - eff)

            #Infection occurs
            if random.random() < prob:
                with country.lock:
                    if target.state == "healthy":
                        target.state = "infected"
                        target.days_infected = 0
                        target.infectious_period = random.randint(*INFECTIOUS_PERIOD_RANGE)
                        allocate_treatment_if_budget(country, target)

    #Daily probability of death while infected
    death_prob = p.death_probability() * DAILY_DEATH_MULTIPLIER
    if p.hospitalized:
        death_prob *= 0.5
    elif high_risk:
        death_prob *= 1.5

    #Death occurs
    if random.random() < death_prob:
        with country.lock:
            if p.hospitalized and country.current_hospitalized > 0:
                country.current_hospitalized -= 1
                p.hospitalized = False
            p.state = "dead"
        return

    p.days_infected += 1

    #Final day
    if p.days_infected >= p.infectious_period:
        treat_prob = treatment_effectiveness.get(p.treatment_type, 0.0) if p.has_treatment else 0.0
        r = random.random()

        #Final death chance
        base_final_death_prob = p.death_probability() * 0.7
        if p.hospitalized:
            base_final_death_prob *= 0.5
        elif high_risk:
            base_final_death_prob *= 1.5

        #Treatment success: Recovery
        if r < treat_prob:
            result = "recovered"

        #Otherwise determine death or recovery
        elif random.random() < base_final_death_prob:
            result = "dead"
        else:
            result = "recovered"

        #Update final state
        with country.lock:
            if p.hospitalized and country.current_hospitalized > 0:
                country.current_hospitalized -= 1
                p.hospitalized = False
            p.state = result
