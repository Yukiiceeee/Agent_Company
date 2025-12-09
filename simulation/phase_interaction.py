import sys
import json
import os
import re
import jieba
import traceback
import autogen
import time
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum, IntEnum

import asyncio
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from utils import extract_json
from api import MODEL_CLIENT
from configs.roles import *
from group.agents.assistant_agent import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from core.teams.company_demander import DemanderTeamFactory_interaction
from core.teams.company_producer import ProducerTeamFactory_interaction

GLOBAL_CONCURRENCY_LIMIT = 5
MAX_ROUNDS = 3

class InteractionLogger:
    """交互阶段专用日志"""
    def __init__(self, filename="../logs/interaction_log.txt"):
        self.filename = filename
        import datetime
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"=== Phase 2 Interaction Log - {datetime.datetime.now()} ===\n\n")
    
    def log_step(self, step_name: str, agent_name: str, content: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = (
            f"[{timestamp}] {step_name}\n"
            f"Agent: {agent_name}\n"
            f"{'─'*60}\n"
            f"{content}\n"
            f"{'='*60}\n\n"
        )
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    def log_summary(self, results: List[InteractionHistory], total_time: float):
        summary = f"""
        {'='*60}
        SIMULATION SUMMARY
        {'='*60}
        Total Interactions: {len(results)}
        Successful: {sum(1 for r in results if r.final_status == 'success')}
        Failed: {sum(1 for r in results if r.final_status == 'failure')}
        Total Time: {total_time:.2f}s
        Average Time: {total_time/len(results) if results else 0:.2f}s

        Detailed Results:
        """
        for i, r in enumerate(results, 1):
            summary += f"\n{i}. {r.demander_name} ↔ {r.producer_name}"
            summary += f"\n   Status: {r.final_status} | Rounds: {r.total_rounds}"
            if r.failure_reason:
                summary += f"\n   Reason: {r.failure_reason}"
        
        summary += f"\n{'='*60}\n"
        
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(summary)
        
        print(summary)


class phase2_workflow:
    def __init__(self, model_client, matched_list: List[Dict], all_companies: List[Company]):
        self.model_client = model_client
        self.matched_list = matched_list
        self.company_map = {c.company_id: c for c in all_companies}
        self.logger = InteractionLogger("../logs/simulation_phase3_interaction_log.txt")
        self.semaphore = asyncio.Semaphore(GLOBAL_CONCURRENCY_LIMIT)

    async def run(self):
        print(f"\n======== Phase 3: Interaction & Execution Start ========")
        start_time = time.time()
        tasks = []

        for match in self.matched_list:
            task = self.process_single_interaction(match)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Match {i+1} failed with exception: {result}")
                self.logger.log_step("Exception", f"Match_{i+1}", str(result))
                traceback.print_exc() # 打印堆栈以便调试
            elif result is None:
                print(f"⚠️ Match {i+1} returned None (Unexpected)")
            else:
                valid_results.append(result)

        end_time = time.time()
        total_duration = end_time - start_time

        print(f"\n======== Phase 3 Completed. Total Interactions: {len(valid_results)}/{len(results)} ========")

        self.logger.log_summary(valid_results, total_duration)

        final_data = [h.to_dict() for h in valid_results]
        try:
            with open("../logs/final_interaction_history.json", "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            print("📁 Final history saved to ../logs/final_interaction_history.json")
        except Exception as e:
            print(f"❌ Failed to save final json: {e}")
            
        return valid_results

    async def process_single_interaction(self, match: Dict) -> InteractionHistory:
        async with self.semaphore:
            demander = self.company_map[match['demander_id']]
            producer = self.company_map[match['producer_id']]
            project_data = match['project']
            
            history = InteractionHistory(
                demander_id=demander.company_id,
                demander_name=demander.name,
                producer_id=producer.company_id,
                producer_name=producer.name,
                project_id=project_data['project_id'],
                project_content=project_data['project_content']
            )
            
            print(f"🚀 Start Interaction: {demander.name} <-> {producer.name}")

            last_review_content = ""
            
            for round_idx in range(1, MAX_ROUNDS + 1):
                print(f"  ⏱️ [Round {round_idx}] {demander.name} <-> {producer.name}")
                
                try:
                    # ==========================================================
                    # Step 1: Producer 生成方案 (ProducerProposal)
                    # ==========================================================
                    producer_team = ProducerTeamFactory_interaction.create_team(
                        producer, round_idx, last_review_content, self.model_client
                    )
                    
                    p_task_input = (
                        f"项目原始需求: {history.project_content}\n"
                        f"Tags: {project_data.get('tags')}\n"
                        f"上一轮反馈: {last_review_content if last_review_content else '无 (初始轮)'}"
                    )
                    
                    p_res = await producer_team.run(task=p_task_input)
                    p_raw = p_res.messages[-1].content
                    self.logger.log_step(f"R{round_idx} Producer Output", producer.name, p_raw)
                    
                    p_json = extract_json(p_raw.replace("TERMINATE", "").strip())
                    if not p_json:
                        raise ValueError("Producer failed to generate valid JSON")

                    proposal_obj = ProducerProposal(
                        version=round_idx,
                        technical_design=p_json.get("technical_design", ""),
                        feature_list=p_json.get("feature_list", []),
                        implementation_plan=p_json.get("implementation_plan", ""),
                        timeline=p_json.get("timeline", ""),
                        risk_analysis=p_json.get("risk_analysis", "")
                    )

                    # ==========================================================
                    # Step 2: Demander 审阅方案 (DemanderReview)
                    # ==========================================================
                    proposal_str_for_review = json.dumps(p_json, ensure_ascii=False, indent=2)
                    
                    demander_team = DemanderTeamFactory_interaction.create_team(
                        demander, proposal_str_for_review, last_review_content, self.model_client
                    )
                    
                    d_task_input = f"请审阅乙方提交的第 {round_idx} 版方案，并给出 JSON 格式的反馈。"
                    
                    d_res = await demander_team.run(task=d_task_input)
                    d_raw = d_res.messages[-1].content
                    self.logger.log_step(f"R{round_idx} Demander Output", demander.name, d_raw)
                    
                    d_json = extract_json(d_raw.replace("TERMINATE", "").strip())
                    if not d_json:
                        raise ValueError("Demander failed to generate valid JSON")

                    review_obj = DemanderReview(
                        overall_satisfaction=d_json.get("overall_satisfaction", "needs_major_revision"),
                        weaknesses=d_json.get("weaknesses", []),
                        additional_requirements=d_json.get("additional_requirements", []),
                        revision_priority=d_json.get("revision_priority", []),
                        expected_improvements=d_json.get("expected_improvements", "")
                    )

                    # ==========================================================
                    # Step 3: 记录本轮交互
                    # ==========================================================
                    round_record = InteractionRound(
                        round_id=round_idx,
                        producer_proposal=proposal_obj,
                        demander_review=review_obj
                    )
                    history.rounds.append(round_record)
                    history.total_rounds = round_idx
                    
                    last_review_content = json.dumps(d_json, ensure_ascii=False, indent=2)

                    # ==========================================================
                    # Step 4: 判断是否结束
                    # ==========================================================
                    status = review_obj.overall_satisfaction
                    print(f"    👉 Result: {status}")

                    history.final_status = "failure"
                    if status == "accepted":
                        history.final_status = "success"
                        history.final_proposal = proposal_obj
                        print(f"    🎉 Success! {demander.name} accepted the proposal.")
                        break
                    
                    if round_idx == MAX_ROUNDS:
                        history.final_status = "failure"
                        history.failure_reason = "Max rounds reached without acceptance."
                        print(f"    ❌ Failed: Max rounds reached.")

                except Exception as e:
                    print(f"    ⚠️ Error in interaction: {e}")
                    traceback.print_exc()
                    history.final_status = "failure"
                    history.failure_reason = str(e)
                    break
            
            return history
        
if __name__ == "__main__":
    print("🚀 Initializing Dummy Data for Phase 3 Testing...")

    # 1. 创建 Demanders
    d1 = Company(
        company_id="D_Ecom", 
        name="ShopifyPlus Inc", 
        role=CompanyRole.DEMANDER,
        description="大型跨境电商平台。",
        details="电商平台。",
        tags=["E-commerce", "High Concurrency"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="开发下一代基于AI的推荐购物引擎。")
    )
    d2 = Company(
        company_id="D_FinTech", 
        name="SecurePay Bank", 
        role=CompanyRole.DEMANDER,
        description="数字银行。",
        details="一家很大的数字银行。",
        tags=["Finance", "Security"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="升级核心账务系统的区块链审计模块。")
    )
    d3 = Company(
        company_id="D_Logistics", 
        name="FastTrack Logistics", 
        role=CompanyRole.DEMANDER,
        description="全球物流公司。",
        details="一家很大的全球物流公司。",
        tags=["Logistics", "IoT"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="构建实时物流追踪IoT平台。")
    )

    # 2. 创建 Producers
    p1 = Company(
        company_id="P_AI_Lab", 
        name="Nebula AI", 
        role=CompanyRole.PRODUCER,
        description="顶级AI算法团队。",
        details="AI算法很强。",
        tags=["AI", "Python", "Recommendation"],
        state=CompanyState.IDLE
    )
    p2 = Company(
        company_id="P_BlockSoft", 
        name="Chain Reactors", 
        role=CompanyRole.PRODUCER,
        description="区块链底层开发专家。",
        details="区块链很强。",
        tags=["Blockchain", "Security", "Go"],
        state=CompanyState.IDLE
    )
    p3 = Company(
        company_id="P_IoT_Sol", 
        name="SmartThings Dev", 
        role=CompanyRole.PRODUCER,
        description="物联网硬件与软件集成。",
        details="物联网很强。",
        tags=["IoT", "Embedded", "Cloud"],
        state=CompanyState.IDLE
    )

    all_companies = [d1, d2, d3, p1, p2, p3]

    # 3. 手动构造匹配列表 (模拟 Phase 1 的输出)
    # 这里的 project 字典模拟了 ActiveProject 对象的属性
    matched_list = [
        {
            "demander_id": d1.company_id,
            "producer_id": p1.company_id,
            "project": {
                "project_id": "proj_ecom_001",
                "project_content": "我们需要一个能支持双十一流量的AI推荐系统，要求响应时间低于50ms，提升转化率20%。",
                "tags": ["AI", "E-commerce"]
            }
        },
        {
            "demander_id": d2.company_id,
            "producer_id": p2.company_id,
            "project": {
                "project_id": "proj_fin_002",
                "project_content": "开发私有链审计系统，记录所有转账操作，确保不可篡改，符合GDPR标准。",
                "tags": ["Blockchain", "Security"]
            }
        },
        {
            "demander_id": d3.company_id,
            "producer_id": p3.company_id,
            "project": {
                "project_id": "proj_log_003",
                "project_content": "连接 50万台 GPS 设备的实时数据平台，需要可视化大屏和异常报警功能。",
                "tags": ["IoT", "BigData"]
            }
        }
    ]

    print(f"✅ Created {len(all_companies)} companies and {len(matched_list)} matches.")

    # 4. 运行模拟
    # 注意：确保 MODEL_CLIENT 已经正确配置
    try:
        workflow = phase2_workflow(MODEL_CLIENT, matched_list, all_companies)
        asyncio.run(workflow.run())
    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped by user.")
    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        traceback.print_exc()