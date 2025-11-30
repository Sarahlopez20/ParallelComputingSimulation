# Parallel Computing Pandemic Simulation

## Overview

This project simulates the spread of a pandemic within a population using parallel computing techniques. It models critical dynamics such as migration, policy interventions, and random events, supporting both in-depth analysis and visual exploration. Simulation results are stored in a database (SQLite) so that it can be later analyzed.

## Features

- **Parallel Simulation Engine**: Accelerates computation of complex models leveraging Python multithreading.
- **Extensible Disease & Population Models**: Customize epidemiological characteristics, migration patterns, and social interactions.
- **Policy & Interventions**: Simulate effects of lockdowns, vaccinations, and other containment strategies.
- **Event System**: Incorporate random or scheduled events that influence simulation outcomes.
- **Data Logging & Analysis**: Results are recorded in an SQLite database for further inspection and visualization.

## Directory Structure

```
Final Project - copia/
├── main.py
├── data/
│   └── simulation.sqlite
├── simulation/
│   ├── __init__.py
│   ├── config.py
│   ├── disease.py
│   ├── events.py
│   ├── logger.py
│   ├── migration.py
│   ├── models.py
│   ├── policies.py
│   ├── simulation.py
│   └── workers.py
└── analysis/
    ├── __init__.py
    ├── analysis_plots.py
    └── interactive_map.py
```

## Prerequisites

- **Python 3.8 or newer**  
  (Recommended: Python 3.10+ for optimal performance)
- **Required packages**:  
  Install dependencies using `pip`

- **OS Compatibility**: Windows, macOS, and Linux

## Quick Start

1. **Install Dependencies**
   Manual installation (see above)

2. **Run the Simulation**
   ```bash
   python main.py
   ```
   - By default, this executes a 30-day simulation and prints completion status on the console.

5. **Analyze the Results**
   Use provided scripts for visualization:
   ```bash
   python analysis/analysis_plots.py
   python analysis/interactive_map.py
   ```
   - Refer to script comments and docstrings for usage details or customization.

## Configuration & Customization

- **Configure Simulation**:  
  Edit values in `simulation/config.py` to change simulation duration, disease parameters, migration, policy triggers, etc.
- **Extend Models/Events/Policies**:  
  Add or modify logic in corresponding modules within the `simulation/` directory.
- **Database Usage**:  
  Access `simulation.sqlite` directly with SQLite-compatible tools or Python’s `sqlite3`/`pandas` for custom analyses.


---

## Acknowledgements

This project was developed as a capstone in parallel computing and simulation.  
Thanks to contributors and users who help advance its capabilities!
