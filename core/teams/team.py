import asyncio
from typing import List
from dataclasses import dataclass
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from group.agents.assistant_agent import AssistantAgent

@dataclass
class MockResponse:
    messages: List[TextMessage]

class ParallelTeam:
    def __init__(self, consultants: List[AssistantAgent], ceo: AssistantAgent):
        self.consultants = consultants
        self.ceo = ceo

    async def run(self, task: str) -> MockResponse:
        """
        执行逻辑：
        1. 并行调用所有 consultants (Business, Tech, Resource)
        2. 收集他们的回复
        3. 将汇总后的意见交给 CEO
        4. 返回 CEO 的最终决策
        """
        input_msg = TextMessage(content=task, source="user")

        # 2. 并行执行 Consultants
        # 注意：这里我们直接调用 agent.on_messages 来获取回复
        # Autogen 0.4+ 的 AssistantAgent 通常有 on_messages 或 run 方法
        # 这里假设使用 on_messages，它返回一个 Response 对象
        
        async def query_agent(agent):
            try:
                response = await agent.on_messages([input_msg], cancellation_token=None)
                return {"role": agent.name, "content": response.chat_message.content}
            except Exception as e:
                print(f"❌ Agent {agent.name} failed: {e}")
                return {"role": agent.name, "content": "（该部门未响应）"}

        consultant_results = await asyncio.gather(
            *[query_agent(agent) for agent in self.consultants]
        )

        aggregated_reports = "【各部门评估报告】\n"
        for res in consultant_results:
            aggregated_reports += f"\n--- {res['role']} ---\n{res['content']}\n"

        ceo_input_content = (
            f"{task}\n\n"
            f"{'='*30}\n"
            f"基于以上原始信息，你的下属部门已经提交了如下评估报告，请参考并做出最终决策（JSON格式）：\n"
            f"{aggregated_reports}"
        )
        
        ceo_msg = TextMessage(content=ceo_input_content, source="system")        
        ceo_response = await self.ceo.on_messages([ceo_msg], cancellation_token=None)

        final_messages = [
            TextMessage(content=task, source="user"),
            TextMessage(content=aggregated_reports, source="system_aggregator"),
            ceo_response.chat_message
        ]
        
        return MockResponse(messages=final_messages)