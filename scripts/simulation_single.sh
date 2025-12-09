#!/bin/bash

PROJECT_ROOT="/data1/wyh/ai-town-x/AgentCompany"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 "$PROJECT_ROOT/simulation/simulation_single.py" \
    --data_path "../data/companies_info.json" \
    >> "$PROJECT_ROOT/logs/simulation_single.log" 2>&1