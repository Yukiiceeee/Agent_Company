#!/bin/bash

PROJECT_ROOT="/data1/wyh/ai-town-x/AgentCompany"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 "$PROJECT_ROOT/simulation/simulation_multi.py" \
    --data_path "../data/companies_info.json" \
    --max_weeks 50 \
    >> "$PROJECT_ROOT/logs/simulation_multi.log" 2>&1