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
from configs.prompts import (
    DEMANDER_BUSINESS_PROMPT_MATCH,
    DEMANDER_TECH_PROMPT_MATCH,
    DEMANDER_RESOURCE_PROMPT_MATCH,
    DEMANDER_CEO_PROMPT_MATCH,
    DEMANDER_BUSINESS_PROMPT_INTERACTION,
    DEMANDER_TECH_PROMPT_INTERACTION,
    DEMANDER_RESOURCE_PROMPT_INTERACTION,
    DEMANDER_CEO_PROMPT_INTERACTION
)

class DemanderTeamFactory_match:
    @staticmethod
    def create_team(company: Company) -> RoundRobinGroupChat:
        """
        创建一个包含 Business, Tech, Resource, CEO 四个角色的轮询工作流团队。
        用于 Phase 1 的需求生成。
        """
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        base_info = {
            "company_name": company.name,
            "company_id": company.company_id,
            "company_description": company.description,
            "company_details": company.details,
            "company_tags": ", ".join(company.tags),
            "company_state": company.state.value
        }

        business_agent = AssistantAgent(
            name=f"Business_Dept_{company.company_id}",
            system_message=DEMANDER_BUSINESS_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        tech_agent = AssistantAgent(
            name=f"Tech_Dept_{company.company_id}",
            system_message=DEMANDER_TECH_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        resource_agent = AssistantAgent(
            name=f"Resource_Dept_{company.company_id}",
            system_message=DEMANDER_RESOURCE_PROMPT_MATCH.format(**base_info),
            model_client=model_client,
        )

        ceo_agent = AssistantAgent(
            name=f"CEO_{company.company_id}",
            system_message=DEMANDER_CEO_PROMPT_MATCH.format(**base_info),
            model_client=json_model_client,
        )

        participants = [
            business_agent, 
            tech_agent, 
            resource_agent, 
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

class DemanderTeamFactory_interaction:
    @staticmethod
    def create_team(company: Company, proposal_str: str, last_review_str: str) -> RoundRobinGroupChat:
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        base_info = {
            "company_name": company.name,
            "company_id": company.company_id,
            "company_description": company.description,
            "company_details": company.details,
            "company_tags": ", ".join(company.tags),
            "company_state": company.state.value,
            "proposal_content": proposal_str,
            "last_review_content": last_review_str if last_review_str else "这是第一轮，请根据当前交付方案开始审阅评估。"
        }

        business_agent = AssistantAgent(
            name=f"Business_Dept_{company.company_id}",
            system_message=DEMANDER_BUSINESS_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        tech_agent = AssistantAgent(
            name=f"Tech_Dept_{company.company_id}",
            system_message=DEMANDER_TECH_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        resource_agent = AssistantAgent(
            name=f"Resource_Dept_{company.company_id}",
            system_message=DEMANDER_RESOURCE_PROMPT_INTERACTION.format(**base_info),
            model_client=model_client,
        )

        ceo_agent = AssistantAgent(
            name=f"CEO_{company.company_id}",
            system_message=DEMANDER_CEO_PROMPT_INTERACTION.format(**base_info),
            model_client=json_model_client,
        )

        participants = [
            business_agent, 
            tech_agent, 
            resource_agent, 
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
            consultants=[business_agent, tech_agent, resource_agent], 
            ceo=ceo_agent
        )

        return team

class DemanderAgentFactory:
    @staticmethod
    def create_agent(company: Company) -> AssistantAgent:
        """
        根据公司信息创建 Demander Agent
        """
        system_message = f"""
        你代表公司: {company.name}。你的角色是战略规划与需求发布经理。
        
        你的任务：
        根据提供的 [Strategic Plan] (战略规划)，构思并生成一个具体的项目需求 (ActiveProject)。
        你需要将模糊的战略转化为明确的研发或业务需求。
        
        输出要求：
        必须严格输出为 JSON 格式，不要包含 Markdown 代码块标记（如 ```json），包含以下字段：
        - project_id: 自动生成的ID (基于公司名简写+随机数, 如 {company.company_id}_p01)
        - project_content: 详细的需求描述 (100字左右)
        - type: 项目类型 (如 "WebDev", "AI_Model", "Logistics")
        - tags: 3-5个关键标签 (List[str])
        
        示例格式:
        {{
            "project_id": "{company.company_id}_p01",
            "project_content": "我们需要开发一个...",
            "type": "AI",
            "tags": ["Python", "LLM"],
        }}
        """
        model_client = MODEL_CLIENT
        json_model_client = JSON_MODEL_CLIENT
        return AssistantAgent(
            name=f"Demander_SA_{company.company_id}",
            system_message=system_message,
            model_client=model_client,
        )