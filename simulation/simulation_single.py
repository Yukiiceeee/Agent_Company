import argparse
import json
import os
import traceback
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum, IntEnum

import asyncio

from utils import extract_json
from api import MODEL_CLIENT
from configs.roles import *

from phase_initialization import async_create_companies_list
from phase_match import phase1_workflow
from phase_interaction import phase2_workflow

async def main(data_path: str):
    print("\n" + "="*60)
    print("🚀 AGENT COMPANY SIMULATION: FULL CYCLE START")
    print("="*60 + "\n")

    total_start_time = time.time()

    # ==================================================================
    # PHASE 1: INITIALIZATION (初始化阶段)
    # ==================================================================
    print(f"📦 [PHASE 1] INITIALIZATION STARTING...")
    print(f"   Reading from: {data_path}")
    
    all_companies = await async_create_companies_list(data_path)
    if not all_companies:
        print("❌ [PHASE 1] Failed: No companies created. Exiting simulation.")
        return

    demanders = [c for c in all_companies if c.role == CompanyRole.DEMANDER]
    producers = [c for c in all_companies if c.role == CompanyRole.PRODUCER]
    
    print(f"✅ [PHASE 1] COMPLETE")
    print(f"   Total Companies: {len(all_companies)}")
    print(f"   Demanders: {len(demanders)}")
    print(f"   Producers: {len(producers)}\n")

    # ==================================================================
    # PHASE 2: MATCHING (匹配阶段)
    # ==================================================================
    print(f"🤝 [PHASE 2] MATCHING STARTING...")
    
    if not demanders or not producers:
        print("❌ [PHASE 2] Failed: Need both Demanders and Producers to proceed.")
        return

    matcher = phase1_workflow(model_client=MODEL_CLIENT)
    matched_list = await matcher.run_simulation(all_companies)
    
    if not matched_list:
        print("⚠️ [PHASE 2] Warning: No matches found. Interaction phase will be skipped.")
        return

    print(f"✅ [PHASE 2] COMPLETE")
    print(f"   Successful Matches: {len(matched_list)}\n")

    # ==================================================================
    # PHASE 3: INTERACTION & EXECUTION (交互阶段)
    # ==================================================================
    print(f"⚔️  [PHASE 3] INTERACTION STARTING...")
    
    interactor = phase2_workflow(
        model_client=MODEL_CLIENT, 
        matched_list=matched_list, 
        all_companies=all_companies
    )
    
    interaction_results = await interactor.run()
    success_count = sum(1 for r in interaction_results if r.final_status == 'success')
    fail_count = sum(1 for r in interaction_results if r.final_status == 'failure')

    print(f"✅ [PHASE 3] COMPLETE")
    print(f"   Interactions Processed: {len(interaction_results)}")
    print(f"   Success Deals: {success_count}")
    print(f"   Failed Deals: {fail_count}\n")

    # ==================================================================
    # SUMMARY (总结)
    # ==================================================================
    total_end_time = time.time()
    duration = total_end_time - total_start_time
    
    print("="*60)
    print("🏁 SIMULATION FINISHED")
    print("="*60)
    print(f"Total Duration: {duration:.2f} seconds")
    print("Logs saved to ../logs/ directory.")
    print("Final History saved to ../logs/final_interaction_history.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full Agent Company Simulation")
    parser.add_argument('--data_path', type=str, default="../data/companies_info.json", help='Path to the companies JSON data file')
    args = parser.parse_args()
    
    os.makedirs("../logs", exist_ok=True)
    
    try:
        asyncio.run(main(args.data_path))
    except KeyboardInterrupt:
        print("\n🛑 Simulation interrupted by user.")
    except Exception as e:
        print(f"\n❌ Critical Simulation Error: {e}")
        import traceback
        traceback.print_exc()


