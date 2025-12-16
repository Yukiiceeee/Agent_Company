import argparse
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum, IntEnum

import asyncio

from utils import extract_json
from api import MODEL_CLIENT
from configs.roles import *

from phase_initialization import async_create_companies_list
from phase_initialization import async_refresh_companies_list
from phase_match import phase1_workflow
from phase_interaction import phase2_workflow


async def simulation(data_path: str, max_weeks: int):
    print("\n" + "="*60)
    print("🚀 MULTI-ROUND AGENT SIMULATION: START")
    print("="*60 + "\n")

    current_week = 1
    total_deals = 0

    print(f"📦 【INIT】 Loading companies from {data_path}...")
    all_companies = await async_create_companies_list(data_path)
    if not all_companies:
        print("❌ [PHASE 1] Failed: No companies created. Exiting simulation.")
        return
    
    while(current_week <= max_weeks):
        print(f"\n📅 {'='*20} WEEK {current_week} {'='*20}")

        released_count = 0
        for company in all_companies:
            if company.state == CompanyState.BUSY:
                if current_week >= company.busy_until:
                    company.state = CompanyState.IDLE
                    company.busy_until = 0
                    print(f"🔓 {company.name} 完成项目，状态恢复为空闲。")
                    released_count += 1
        if released_count > 0:
            print(f"ℹ️ 本周共有 {released_count} 家企业释放回市场。")

        active_candidates = [c for c in all_companies if c.state == CompanyState.IDLE]
        demanders = [c for c in active_candidates if c.role == CompanyRole.DEMANDER]
        producers = [c for c in active_candidates if c.role == CompanyRole.PRODUCER]
        print(f"📊 本周市场动态: Demander({len(demanders)}) & Producer({len(producers)})")

        if not demanders or not producers:
            print("😴 本周市场冷清，跳过匹配交互。")
            current_week += 1
            continue
        
        if current_week > 1:
            print(f"📦 【INIT】 开始新一轮的企业初始化...")
            await async_refresh_companies_list(active_candidates, current_week)

        print(f"🤝 【Match】 开始匹配...")
        matcher = phase1_workflow(model_client=MODEL_CLIENT)
        matched_list = await matcher.run_simulation(active_candidates)

        if not matched_list:
            print("⚠️ 本周无匹配产生。")
        else:
            print(f"⚔️ 【Interaction】 开始 {len(matched_list)} 组交互...")
            interactor = phase2_workflow(
                model_client=MODEL_CLIENT,
                matched_list=matched_list,
                all_companies=active_candidates
            )
            interaction_results = await interactor.run()

            for res in interaction_results:
                project_weeks = 4
                for m in matched_list:
                    if m['project']['project_id'] == res.project_id:
                        project_weeks = m['project'].get('weeks', 4) # 默认4周
                        break
                d_company = next(c for c in all_companies if c.company_id == res.demander_id)
                p_company = next(c for c in all_companies if c.company_id == res.producer_id)

                unlock_week = current_week + project_weeks
                d_company.state = CompanyState.BUSY
                d_company.busy_until = unlock_week
                # 这里没有写project_history的实质更新，需要补上
                # 实际上，这个history不会这么简单，应该包含项目的交互内容，以及交互结果等
                d_company.project_history.append(f"Week {current_week}: 与 {p_company.name} 达成合作，项目周期 {project_weeks} 周。")
                p_company.state = CompanyState.BUSY
                p_company.busy_until = unlock_week
                p_company.project_history.append(f"Week {current_week}: 承接 {d_company.name} 需求，项目周期 {project_weeks} 周。")
                
                print(f"🔒 锁定: {d_company.name} & {p_company.name} (直到 Week {unlock_week})")
                total_deals += 1

            success_count = sum(1 for r in interaction_results if r.final_status == 'success')
            fail_count = sum(1 for r in interaction_results if r.final_status == 'failure')
            print(f"✅ 【Interaction】 COMPLETE")
            print(f"   Interactions Processed: {len(interaction_results)}")
            print(f"   Success Deals: {success_count}")
            print(f"   Failed Deals: {fail_count}\n")
            
            # 这里交互结束，应该搭配上多轮交互强化更新的逻辑
            # 对交互结果history获取，并更新memory等方式，强化下一轮agent的system
        
        print(f"✅ Week {current_week} 结束。")
        current_week += 1

    print("\n" + "="*60)
    print(f"🏁 仿真结束 (Total Deals: {total_deals})")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full Agent Company Simulation")
    parser.add_argument('--data_path', type=str, default="../data/companies_info.json", help='Path to the companies JSON data file')
    parser.add_argument('--max_weeks', type=int, default=50, help='Maximum number of weeks to run the simulation')
    args = parser.parse_args()
    
    os.makedirs("../logs", exist_ok=True)
    data_path = args.data_path
    max_weeks = args.max_weeks

    asyncio.run(simulation(data_path=data_path, max_weeks=max_weeks))

