#MAIN
from simulation.simulation import build_default_world

if __name__ == "__main__":
    #Build the whole simulation
    sim = build_default_world(db_path="data/simulation.sqlite")
    #Run the simulation for 30 days
    sim.run(max_days=30)
    print("\nSimulation complete.")
