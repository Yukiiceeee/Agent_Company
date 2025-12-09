import sys
import json
import os
import re
import jieba
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
from core.market import *
from core.teams.company_demander import DemanderAgentFactory
from core.teams.company_producer import ProducerAgentFactory
from core.teams.company_demander import DemanderTeamFactory_match
from core.teams.company_producer import ProducerTeamFactory_match
from group.agents.assistant_agent import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

GLOBAL_CONCURRENCY_LIMIT = 5

class SimulationLogger:
    def __init__(self, filename="../logs/simulation_phase2_match_log.txt"):
        self.filename = filename
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"=== Simulation Started at {datetime.now()} ===\n\n")

    def log_step(self, step_name: str, agent_name: str, content: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = (
            f"[{timestamp}] === {step_name} ===\n"
            f"👤 Agent: {agent_name}\n"
            f"📝 Content:\n{content}\n"
            f"{'-'*60}\n\n"
        )
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"  [Log Saved] {step_name} - {agent_name}")

class phase1_workflow:
    def __init__(self, model_client):
        self.model_client = model_client
        self.matched_list = []
        self.logger = SimulationLogger()
        self.semaphore = asyncio.Semaphore(GLOBAL_CONCURRENCY_LIMIT)

    async def run_simulation(self, all_companies: List[Company]):
        demanders = [c for c in all_companies if c.role == CompanyRole.DEMANDER]
        producers = [c for c in all_companies if c.role == CompanyRole.PRODUCER]

        print(f"======== Simulation Initialized ========")
        print(f"Demanders Count: {len(demanders)}")
        print(f"Producers Count: {len(producers)}")

        start_time = time.time()
        tasks = []

        for demander in demanders:
            print(f"\n----------------------------------------------------")
            print(f"🔄 Processing Demander: {demander.name} ({demander.company_id})")

            task = self.process_single_demander_flow(demander, producers)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
            # active_project = await self._process_demander_proposal_demo(demander)
            # if not active_project:
            #     print(f"   ❌ No project generated for {demander.name}")
            #     continue

            # print(f"🔍 Market System Matching...")
            # # 注意：这里每次实例化 Market，是为了保证每次传入的 producer 列表是全量的
            # # 如果需要动态剔除已匹配的 Producer，可以在这里通过判断state是否为busy来过滤 producers 列表
            # rec_sys = RecommendationSystem(producers)
            # candidates = rec_sys.recommend(active_project, top_k=3)

            # if not candidates:
            #     print(f"  ❌ for this demander {demander.name} -> No suitable producers found.")
            #     self.logger.log_step("Market Match", "System", f"No candidates for {demander.name}")
            #     continue

            # await self._process_producer_bidding_demo(demander, active_project, candidates)

        print(f"\n====================================================")
        print(f"✅ Phase 1 Completed. Total Matches: {len(self.matched_list)}")
        print(json.dumps(self.matched_list, indent=2, ensure_ascii=False))
        self.logger.log_step("Phase 1 Result", "System", json.dumps(self.matched_list, indent=2, ensure_ascii=False))

        end_time = time.time()
        print(f"Total Time: {end_time - start_time:.2f} seconds")
        self.logger.log_step("Phase 1 Time", "System", f"{end_time - start_time:.2f} seconds")

        return self.matched_list
    
    async def process_single_demander_flow(self, demander: Company, all_producers: List[Company]):
        print(f"\n🚀 Start Flow: {demander.name}")
        async with self.semaphore:
            active_project = await self._process_demander_proposal(demander)
        if not active_project:
            print(f"   ❌ [Flow End] {demander.name}: No project generated.")
            return
        
        # 只有当producer的状态不为busy时才可以参与竞标
        active_producers = [p for p in all_producers if p.state != CompanyState.BUSY]
        rec_sys = RecommendationSystem(active_producers)
        candidates = rec_sys.recommend(active_project, top_k=3)

        if not candidates:
            print(f"   ❌ [Flow End] {demander.name}: No suitable producers found.")
            self.logger.log_step("Market Match", "System", f"No candidates for {demander.name}")
            return
        
        match_result = await self._process_producer_bidding_concurrent(demander, active_project, candidates)

        if match_result:
            self.matched_list.append(match_result)
            print(f"   🎉 [Match Confirmed] {demander.name} <--> {match_result['producer_name']}")
        else:
            print(f"   💨 [Flow End] {demander.name}: All candidates rejected.")

    async def _process_single_producer_bid(self, demander: Company, project: ActiveProject, candidate: Dict) -> Optional[Dict]:
        producer = candidate["company"]
        score = candidate["total_score"]
        
        async with self.semaphore:
            try:
                producer_team = ProducerTeamFactory_match.create_team(producer, self.model_client)
                
                rfp_message = json.dumps({
                    "project_content": project.project_content,
                    "required_tags": project.tags,
                }, ensure_ascii=False)
                rfp_input = f"New RFP Received: {rfp_message}"
                
                result = await producer_team.run(task=rfp_input)
                p_content = result.messages[-1].content
                self.logger.log_step("Producer Team Decision", producer.name, p_content)
                
                clean_content = p_content.replace("TERMINATE", "").strip()
                decision_data = extract_json(clean_content)
                
                if decision_data.get("decision") == "ACCEPT":
                    # 这里将当前producer设为busy
                    producer.state = CompanyState.BUSY
                    reason = decision_data.get('reason')
                    print(f"      ✅ {producer.name} Accepted!")
                    return {
                        "demander_id": demander.company_id,
                        "demander_name": demander.name,
                        "producer_id": producer.company_id,
                        "producer_name": producer.name,
                        "project": project.__dict__,
                        "match_reason": reason,
                        "score": score
                    }
                else:
                    print(f"      ❌ {producer.name} Rejected.")
                    return None
                    
            except Exception as e:
                print(f"      ⚠️ Error in producer bid {producer.name}: {e}")
                self.logger.log_step("Error", producer.name, str(e))
                return None
    
    async def _process_demander_proposal(self, demander: Company) -> Optional[ActiveProject]:
        try:
            # print(f"   ⚡ Generating Proposal for {demander.name}...")
            demander_team = DemanderTeamFactory_match.create_team(demander, self.model_client)
            plan_input = f"Current Strategy Plan: {demander.strategy.content}"
            
            result = await demander_team.run(task=plan_input)
            
            last_message_content = result.messages[-1].content
            self.logger.log_step("Demander Team Discussion", demander.name, last_message_content)
            clean_content = last_message_content.replace("TERMINATE", "").strip()
            project_data = extract_json(clean_content)
            
            if not project_data:
                raise ValueError("JSON parsing failed")

            project = ActiveProject(
                project_id=project_data.get("project_id", f"{demander.company_id}_{datetime.now().timestamp()}"),
                project_content=project_data.get("project_content", ""),
                type=project_data.get("type", "General"),
                tags=project_data.get("tags", []),
            )
            print(f"   📝 [Project Ready] {demander.name}: {project.tags}")
            return project
            
        except Exception as e:
            print(f"   ❌ Error generating proposal for {demander.name}: {e}")
            self.logger.log_step("Error", demander.name, str(e))
            return None
        
    async def _process_producer_bidding_concurrent(self, demander: Company, project: ActiveProject, candidates: List[Dict]) -> Optional[Dict]:
        print(f"   🔍 Bidding: {demander.name} asking {len(candidates)} candidates concurrently...")
        
        bid_tasks = []
        for cand in candidates:
            task = self._process_single_producer_bid(demander, project, cand)
            bid_tasks.append(task)
        
        results = await asyncio.gather(*bid_tasks)
        
        accepted_results = [r for r in results if r is not None]
        
        if not accepted_results:
            return None
        
        # 选择最佳匹配
        # 因为我们之前已经按 score 推荐了 top-k，但这里是并发回来的，顺序可能不确定。
        # 策略A：选分数最高的 Accept
        # 策略B：选列表里的第一个 Accept (因为 candidates 本身是有序的，但 gather 结果也是对应 input 顺序的)
        
        # 由于 asyncio.gather 返回的结果顺序与 tasks 列表顺序一致，
        # 而 tasks 是根据 candidates (已经按分数排序) 创建的，
        # 所以 results[0] 就是分数最高的候选人的结果。
        
        # 我们直接取第一个 Accept 即可，这就是“优先级最高的愿意合作者”
        best_match = accepted_results[0]
        
        print(f"      ✅ {demander.name} received {len(accepted_results)} offers. Chose: {best_match['producer_name']}")
        return best_match
    



    async def _process_demander_proposal_demo(self, demander: Company) -> ActiveProject:
        try:
            demander_team = DemanderTeamFactory_match.create_team(demander, self.model_client)
            plan_input = f"Current Strategy Plan: {demander.strategy.content}"
            
            result = await demander_team.run(task=plan_input)
            
            last_message_content = result.messages[-1].content
            self.logger.log_step("Demander Team Discussion", demander.name, last_message_content)
            clean_content = last_message_content.replace("TERMINATE", "").strip()
            project_data = extract_json(clean_content)
            
            if not project_data:
                raise ValueError("JSON parsing failed")

            project = ActiveProject(
                project_id=project_data.get("project_id", f"{demander.company_id}_{datetime.now().timestamp()}"),
                project_content=project_data.get("project_content", ""),
                type=project_data.get("type", "General"),
                tags=project_data.get("tags", []),
            )
            print(f"   📝 Generated Project: [{project.project_id}] {project.tags}")
            return project
            
        except Exception as e:
            print(f"   ❌ Error generating proposal for {demander.name}: {e}")
            self.logger.log_step("Error", demander.name, str(e))
            return None

    async def _process_producer_bidding_demo(self, demander: Company, project: ActiveProject, candidates: List[Dict]):
        match_found = False
        
        for cand in candidates:
            # 【待完善】这里暂时写的是只匹配第一个，假设已经匹配到，那么直接break就用这个匹配到的producer
            if match_found: 
                break
            
            producer = cand["company"]
            score = cand["total_score"]
            print(f"   👉 Asking Candidate: {producer.name} (Matched Score: {score})")
            
            producer_team = ProducerTeamFactory_match.create_team(producer, self.model_client)
            
            rfp_message = json.dumps({
                "project_content": project.project_content,
                "required_tags": project.tags,
            }, ensure_ascii=False)
            rfp_input = f"New RFP Received: {rfp_message}"
            
            try:
                result = await producer_team.run(task=rfp_input)
                p_content = result.messages[-1].content
                self.logger.log_step("Producer Team Decision", producer.name, p_content)
                clean_content = p_content.replace("TERMINATE", "").strip()
                decision_data = extract_json(clean_content)
                
                if decision_data.get("decision") == "ACCEPT":
                    reason = decision_data.get('reason')
                    print(f"      ✅ ACCEPTED! Reason: {reason}")
                    
                    self.matched_list.append({
                        "demander_id": demander.company_id,
                        "demander_name": demander.name,
                        "producer_id": producer.company_id,
                        "producer_name": producer.name,
                        "project": project.__dict__,
                        "match_reason": reason
                    })
                    # 在这里匹配完成，将match_found设为True
                    # 【待完善】可以在这里把 producer 状态改为 BUSY，后续多轮交互逻辑使用
                    # 【待完善】这里并没有实现“产品交付天数”的设定，后续可以在初步生成需求时加上完成天数预估
                    match_found = True
                else:
                    print(f"      ❌ REJECTED. Reason: {decision_data.get('reason')}")
                    
            except Exception as e:
                print(f"      ⚠️ Error parsing producer response: {e}")
                self.logger.log_step("Error", producer.name, str(e))

if __name__ == "__main__":
    # 【待完善】这里应该是初始化阶段把所有Company定义好，然后统一传入
    # 1. Demanders (需求方)
    d1 = Company(
        company_id="D_Retail", 
        name="Global Retail Corp", 
        role=CompanyRole.DEMANDER,
        description="传统零售巨头，寻求电商化。",
        details="我们是一家拥有大量实体店的传统零售商，正在寻求转型。我们希望构建一个高并发的电商平台，并集成AI推荐系统。",
        tags=["Retail"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="2025目标：构建高并发电商平台，集成AI推荐系统。")
    )
    d2 = Company(
        company_id="D_Finance", 
        name="Safe Bank Ltd", 
        role=CompanyRole.DEMANDER,
        description="一家关注数据隐私的商业银行。",
        details="我们是一家重视数据隐私的商业银行，希望确保我们的核心交易系统安全可靠。我们还需要一套审计系统来跟踪交易。",
        tags=["Finance", "Security"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="我们需要升级核心交易系统的防火墙，并开发一套基于区块链的审计系统。")
    )

    # 2. Producers (供给方)
    p1 = Company(
        company_id="P_WebBasic",
        name="Simple Web Studio",
        role=CompanyRole.PRODUCER,
        description="擅长HTML/CSS/Wordpress建站，技术栈简单。",
        details="我们是一家专注于基础建站的团队，擅长使用HTML/CSS/Wordpress。我们希望为中小企业提供快速、可靠的建站服务。",
        tags=["Web", "CMS"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="接中小企业官网外包。")
    )
    p2 = Company(
        company_id="P_AI_Tech",
        name="DeepMind Solutions",
        role=CompanyRole.PRODUCER,
        description="AI独角兽，擅长Python, PyTorch, 推荐算法。",
        details="我们是一家AI独角兽公司，擅长Python, PyTorch, 推荐算法。我们专注于高难度AI模型落地。",
        tags=["AI", "Python", "DataScience"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="专注于高难度AI模型落地。")
    )
    p3 = Company(
        company_id="P_Sec_Ops",
        name="IronClad Security",
        role=CompanyRole.PRODUCER,
        description="网络安全专家，擅长渗透测试和区块链开发。",
        details="我们是一家网络安全专家，擅长渗透测试和区块链开发。我们专注于为金融行业提供定制化安全解决方案。",
        tags=["Security", "Blockchain", "Java"],
        state=CompanyState.IDLE,
        strategy=StrategicPlan(content="提供金融级安全服务。")
    )

    all_companies = [d1, d2, p1, p2, p3]

    model_client = MODEL_CLIENT
    workflow = phase1_workflow(model_client=model_client)
    asyncio.run(workflow.run_simulation(all_companies))