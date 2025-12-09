import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum, IntEnum
from datetime import datetime

class CompanyRole(Enum):
    DEMANDER = "Demander"
    PRODUCER = "Producer"
    USER = "User"

class CompanyState(Enum):
    IDLE = "Idle"    
    BUSY = "Busy"     
    OTHER = "Other"   

@dataclass
class StrategicPlan:
    content: str = "" # 主要的计划内容
    annual_plan: str = ""      
    quarterly_plan: str = ""    
    monthly_plan: str = ""

@dataclass
class ActiveProject:
    project_id: str          
    project_content: str       
    type: str            
    tags: List[str] = field(default_factory=list) 

class Company:
    def __init__(self, 
                 company_id: str,
                 name: str,
                 role: CompanyRole,
                 description: str,
                 details: str,
                 tags: List[str],
                 state: CompanyState,
                 strategy: Optional[StrategicPlan] = None,):
        
        self.company_id: str = company_id
        self.name: str = name
        self.role: CompanyRole = role
        self.description: str = description
        self.details: str = details
        self.tags: List[str] = tags
        self.strategy: StrategicPlan = strategy
        self.state: CompanyState = state

    def __repr__(self):
        return f"<Company {self.name} ({self.role.value})>"


# Interaction Roles
@dataclass  
class ProducerProposal:
    """Producer 交付方案结构 (对应 JSON 输出)"""
    version: int
    technical_design: str      # 技术架构设计
    feature_list: List[str]    # 功能点列表
    implementation_plan: str   # 实施计划
    timeline: str              # 时间线
    risk_analysis: str         # 风险分析

@dataclass
class DemanderReview:
    """Demander 审阅报告结构 (对应 JSON 输出)"""
    overall_satisfaction: str  # "accepted" / "needs_major_revision" / "needs_minor_revision"
    weaknesses: List[str]      # 方案缺陷
    additional_requirements: List[str]  # 新增需求
    revision_priority: List[str]        # 修改优先级
    expected_improvements: str          # 期望改进方向

@dataclass
class InteractionRound:
    """单轮交互记录"""
    round_id: int
    producer_proposal: ProducerProposal # 嵌套对象
    demander_review: DemanderReview     # 嵌套对象
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return {
            "round_id": self.round_id,
            "timestamp": self.timestamp,
            "producer_proposal": self.producer_proposal.__dict__,
            "demander_review": self.demander_review.__dict__
        }

@dataclass
class InteractionHistory:
    """完整交互历史"""
    demander_id: str
    demander_name: str
    producer_id: str
    producer_name: str
    project_id: str
    project_content: str
    
    rounds: List[InteractionRound] = field(default_factory=list)
    final_status: str = "pending"  # "success" / "failure" / "pending"
    total_rounds: int = 0
    final_proposal: Optional[ProducerProposal] = None
    failure_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "meta": {
                "demander": {"id": self.demander_id, "name": self.demander_name},
                "producer": {"id": self.producer_id, "name": self.producer_name},
                "project": {"id": self.project_id, "content": self.project_content}
            },
            "summary": {
                "total_rounds": self.total_rounds,
                "final_status": self.final_status,
                "failure_reason": self.failure_reason
            },
            "history": [r.to_dict() for r in self.rounds]
        }