#!/bin/bash

PROJECT_ROOT="/data1/wyh/ai-town-x/AgentCompany"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 "$PROJECT_ROOT/simulation/phase_initialization.py" \
    --data_path "../data/companies_info.json" \
    >> "$PROJECT_ROOT/logs/simulation_initialization.log" 2>&1