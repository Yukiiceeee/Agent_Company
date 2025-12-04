#!/bin/bash

PROJECT_ROOT="/data1/wyh/ai-town-x/AgentCompany"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 "$PROJECT_ROOT/simulation/phase_match.py" >> "$PROJECT_ROOT/logs/simulation_match.log" 2>&1