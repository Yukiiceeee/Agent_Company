import os
import json
import asyncio
import traceback
import autogen
import sys
from typing import List
from group.agents.assistant_agent import AssistantAgent
from group.group_chat.round_robin_group_chat import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from api import MODEL_CLIENT
from api import JSON_MODEL_CLIENT
from core.teams.team import ParallelTeam

from configs.roles import *
# 统一的提示词在这里写入并传入
from configs.prompts import (
    PRODUCER_SALES_PROMPT_MATCH,
    PRODUCER_PRODUCT_PROMPT_MATCH,
    PRODUCER_TECH_PROMPT_MATCH,
    PRODUCER_CEO_PROMPT_MATCH,
    PRODUCER_SALES_PROMPT_INTERACTION,
    PRODUCER_PRODUCT_PROMPT_INTERACTION,
    PRODUCER_TECH_PROMPT_INTERACTION,
    PRODUCER_CEO_PROMPT_INTERACTION
)

class ProducerTeamFactory_match:
    @staticmethod
    def create_team(company: Company) -> RoundRobinGroupChat:
        """
        创建一个包含 Sales, Product, Tech, CEO 四个角色的轮询工作流团队。
        用于 Phase 1 的竞标决策。
        """
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        base_info = {
            "company_name": company.name,
            "company_id": company.company_id,
            "company_description": company.description,
            "company_details":company.details,
            "company_tags": ", ".join(company.tags),
            "company_state": company.state.value
        }
        
        sales_agent = AssistantAgent(
            name=f"Sales_Dept_{company.company_id}",
            system_message=PRODUCER_SALES_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        product_agent = AssistantAgent(
            name=f"Product_Dept_{company.company_id}",
            system_message=PRODUCER_PRODUCT_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        tech_agent = AssistantAgent(
            name=f"Tech_Dept_{company.company_id}",
            system_message=PRODUCER_TECH_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        ceo_agent = AssistantAgent(
            name=f"CEO_{company.company_id}",
            system_message=PRODUCER_CEO_PROMPT_MATCH.format(**base_info),
            model_client=json_model_client,
        )

        participants = [
            sales_agent, 
            product_agent, 
            tech_agent, 
            ceo_agent
        ]

        # 定义终止条件 (Termination Condition)
        # 条件 A: CEO 说出了 "TERMINATE" 关键词 (暂废除)
        text_termination = TextMentionTermination(text="TERMINATE")
        # 条件 B: 防止死循环，设置最大轮数 (注意这里还包含一个user message)
        max_msg_termination = MaxMessageTermination(max_messages=5)
        
        termination_condition = max_msg_termination

        # team = RoundRobinGroupChat(
        #     participants=participants,
        #     termination_condition=termination_condition
        # )

        team = ParallelTeam(
            consultants=[sales_agent, tech_agent, product_agent], 
            ceo=ceo_agent
        )

        return team
    
class ProducerTeamFactory_interaction:
    @staticmethod
    def create_team(company: Company, round_id: int, last_review_str: str) -> RoundRobinGroupChat:
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        base_info = {
            "company_name": company.name,
            "company_id": company.company_id,
            "company_description": company.description,
            "company_details":company.details,
            "company_tags": ", ".join(company.tags),
            "company_state": company.state.value,
            "round_id": round_id,
            "last_review_content": last_review_str if last_review_str else "这是第一轮，请根据原始需求文档开始设计。"
        }
        
        sales_agent = AssistantAgent(
            name=f"Sales_Dept_{company.company_id}",
            system_message=PRODUCER_SALES_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        product_agent = AssistantAgent(
            name=f"Product_Dept_{company.company_id}",
            system_message=PRODUCER_PRODUCT_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        tech_agent = AssistantAgent(
            name=f"Tech_Dept_{company.company_id}",
            system_message=PRODUCER_TECH_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        ceo_agent = AssistantAgent(
            name=f"CEO_{company.company_id}",
            system_message=PRODUCER_CEO_PROMPT_INTERACTION.format(**base_info),
            model_client=json_model_client,
        )

        participants = [
            sales_agent, 
            # product_agent, 
            # tech_agent, 
            ceo_agent
        ]

        # 定义终止条件 (Termination Condition)
        # 条件 A: CEO 说出了 "TERMINATE" 关键词 (暂废除)
        text_termination = TextMentionTermination(text="TERMINATE")
        # 条件 B: 防止死循环，设置最大轮数 (注意这里还包含一个user message)
        max_msg_termination = MaxMessageTermination(max_messages=5)
        
        termination_condition = max_msg_termination

        team = RoundRobinGroupChat(
            participants=participants,
            termination_condition=termination_condition
        )

        return team











class ProducerAgentFactory:
    @staticmethod
    def create_agent(company: Company) -> AssistantAgent:
        """
        根据公司信息创建 Producer Agent
        """
        system_message = f"""
        你代表公司: {company.name}。你的角色是商务总监。
        公司简介: {company.description}
        公司标签: {company.tags}
        当前状态: {company.state.value}
        
        你的任务：
        接收并评估一个项目需求 (Project Requirement)。
        根据公司的技术栈、业务方向和当前忙碌状态，决定是否接受这个项目。
        
        决策逻辑：
        1. 技术栈匹配：仔细对比我们的Tags和需求的Tags。
        2. 状态检查：如果我们是 Busy 状态，必须有极高的理由才接受。
        
        输出要求：
        必须严格输出为 JSON 格式，不要包含 Markdown 代码块标记，包含以下字段：
        - decision: "ACCEPT" 或 "REJECT"
        - reason: 简短的决策理由 (如果拒绝，请说明具体原因)
        """
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        
        return AssistantAgent(
            name=f"Producer_SA_{company.company_id}",
            system_message=system_message,
            model_client=model_client,
        )