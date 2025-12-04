import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum, IntEnum

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