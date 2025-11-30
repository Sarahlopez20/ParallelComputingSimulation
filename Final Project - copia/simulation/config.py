#PARAMETERS FOR THE SIMULATION

#Number of patients per country
NUM_PATIENTS_PER_COUNTRY = 500

#Initial infected proportion
INITIAL_INFECTED_FRAC = 0.10

#Base transmission probability per contact
TRANSMISSION_BASE = 0.30

#Range of daily contacts per person
CONTACTS_RANGE = (2, 5)

#Higher transmission for superspreaders
SUPERSPREADER_MULTIPLIER = 3

#Protection level provided by masks
MASK_EFFECTIVENESS = 0.5

#Duration (days) a person stays infectious
INFECTIOUS_PERIOD_RANGE = (4, 7)

#Daily mortality for infected individuals
DAILY_DEATH_MULTIPLIER = 0.2

#Base probability of traveling between countries per day
BASE_TRAVEL_PROB = 0.05

#Fraction of contacts kept under lockdown, reducing 60& the contacts
LOCKDOWN_CONTACT_FACTOR = 0.4


#Variant introduced mid-simulation
VARIANT_DAY = 15
VARIANT_TRANSMISSION_MULTIPLIER = 1.5    #How much more contagious it is
VARIANT_VACCINE_EFFECTIVENESS_DROP = 0.3 #Reduction in vaccine protection


#Treatment and vaccine effectiveness
treatment_effectiveness = {"T1": 0.75, "T2": 0.6}
vaccine_effectiveness   = {"A": 0.9, "B": 0.7, "C": 0.5}


#Vaccination campaign
VACCINATION_CAMPAIGN_DAY = 10
VACCINE_COST = {"A": 3, "B": 2, "C": 1}
TREATMENT_COST = 1
