#!/bin/bash

PROJECT_ROOT="/data1/wyh/ai-town-x/AgentCompany"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

python3 "$PROJECT_ROOT/simulation/phase_interaction.py" >> "$PROJECT_ROOT/logs/simulation_interaction.log" 2>&1