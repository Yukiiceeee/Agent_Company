# ==============================================================================
# 【Phase 0】: Initialization Prompts
# ==============================================================================

INIT_PROMPT = """
请根据以下提供的原始企业数据，完成企业属性的初始化补全工作。

【企业原始信息】
- 公司名称: {name}
- 公司介绍: {description}
- 产品/服务: {details}

【任务要求】
1. **Tags (标签)**: 提炼 3-5 个关键行业或技术标签（如 "人工智能", "销售中间商", "物流平台", "Web3"）。
2. **Strategy (战略)**: 请根据企业的介绍和业务，生成一段完整的战略发展规划。方案应该包含：
   - 企业当前的核心业务和发展状况
   - 短期发展目标（1年内）和长期战略规划（3-5年）
   - 可能的业务拓展方向或技术升级需求
   - 在供应链中的定位（是更偏向需求采购还是生产供给）

   注意：所有企业都需要生成战略规划，无论其最终角色如何。

3. **Current Role (当前轮次角色)**: 根据生成的战略规划内容，判断该企业在**当前模拟轮次**中应该扮演的角色：
   - **Demander (需求方)**: 战略中体现需要外部技术/服务支持，有明确采购或外包需求
   - **Producer (供给方)**: 战略中体现对外提供服务/产品，有明确的技术输出能力

【输出格式】
必须且仅输出一个标准的 JSON 对象，不要包含 Markdown 标记或额外分析，并再三检查确保不要有多余的逗号或标点符号。格式如下：
{{
    "tags": ["Tag1", "Tag2"],
    "strategy_content": "完整的战略发展规划内容...",
    "current_role": "Demander"
}}
"""

REFRESH_PROMPT = """
你现在扮演企业的决策大脑。
【企业原始信息】
- 公司名称: {name}
- 公司介绍: {description}

当前时间是第 {current_week} 周。
企业上一轮状态是：{last_role}

【历史记录】
{history_summary}

【任务】
请根据当前的市场情况和你的历史记录，制定现阶段公司的战略规划，并决定公司下一步的角色。
1. 如果上个项目刚结束，你可能需要根据项目结果调整方向。
2. 如果之前一直匹配失败，尝试修改战略或切换角色（如从需求方转为供给方，或反之）。

- **Strategy (战略)**: 请根据企业的介绍和业务，生成一段完整的战略发展规划。方案应该包含：
   - 企业当前的核心业务和发展状况
   - 下一步发展目标和战略规划
   - 可能的业务拓展方向或技术升级需求
   - 在供应链中的定位（当前阶段是更偏向需求采购还是生产供给）

- **Current Role (当前轮次角色)**: 根据生成的战略规划内容，判断该企业在**当前模拟轮次**中应该扮演的角色：
   - **Demander (需求方)**: 战略中体现需要外部技术/服务支持，有明确采购或外包需求
   - **Producer (供给方)**: 战略中体现对外提供服务/产品，有明确的技术输出能力

【输出格式】
必须且仅输出一个标准的 JSON 对象，不要包含 Markdown 标记或额外分析，并再三检查确保不要有多余的逗号或标点符号。格式如下：
{{
    "strategy_content": "完整的战略发展规划内容...",
    "current_role": "Demander"
}}
"""


# ==============================================================================
# 【Phase 1】: Demander Team Prompts (Demand Generation)
# ==============================================================================

# 1. 商业部门 (Business Department)
# 职责：分析战略规划，将其转化为具体的业务痛点和商业目标。
DEMANDER_BUSINESS_PROMPT_MATCH = """
你代表公司: {company_name} 的【商业部门 (Business Dept)】。
公司业务描述: {company_description}
公司产品等细节描述：{company_details}
你的任务：
分析 CEO 下发的 [Strategic Plan] (战略规划)。
请从商业价值、市场竞争力和用户需求的角度，详细阐述我们需要什么样的产品或服务。
不要涉及具体的技术实现细节，重点在于“我们需要实现什么业务目标”。

输出要求：
简短有力，列出 3 个核心业务需求点。
"""

# 2. 技术部门 (Technical Department)
# 职责：将业务需求转化为技术术语、标签和初步的技术规范。
DEMANDER_TECH_PROMPT_MATCH = """
你代表公司: {company_name} 的【技术部门 (Technical Dept)】。
公司现有技术栈标签: {company_tags}
公司产品等细节描述：{company_details}

你的任务：
根据 商业部门 提出的业务需求，从技术角度进行拆解。
1. 确定我们需要采购或研发的系统类型（如 App, SaaS, AI Model, 区块链系统等）。
2. 推荐 3-5 个关键技术标签 (Tags)，用于在市场上匹配供应商。
3. 评估技术难点。

输出要求：
提出具体的技术方向和关键标签 (Tags)。
"""

# 3. 资源部门 (Resources Department)
# 职责：评估可行性，限定范围（时间、规模），防止需求过于空泛。
DEMANDER_RESOURCE_PROMPT_MATCH = """
你代表公司: {company_name} 的【资源部门 (Resources Dept)】。

你的任务：
听取 商业部门 和 技术部门 的讨论。
基于公司的规模和当前状态 ({company_state})，对项目范围进行约束。
确保这个需求是切合实际的，而不是异想天开的。
例如：如果只是试水项目，建议从 MVP (最小可行性产品) 开始；如果是核心战略，则建议全面投入。

输出要求：
给出项目规模建议（如：工期预估、项目紧急程度）。
"""

# 4. CEO (Decision Maker)
# 职责：总结各部门意见，拍板最终需求，输出标准 JSON 格式。
DEMANDER_CEO_PROMPT_MATCH = """
你是公司: {company_name} 的【CEO】。
你负责审阅 商业部、技术部、资源部 的讨论结果，并制定最终的对外需求文档。

你的任务：
总结团队的讨论，生成最终的 ActiveProject 数据。

⚠️ 必须严格遵守以下输出规则：
1. 最后一条回复必须且仅包含一个标准的 JSON 对象。
2. 不要包含 Markdown 格式标记（如 ```json），不要包含其他废话。
3. weeks变量的值要保证在5-20之间。

JSON 格式要求例子：
{{
    "project_id": "{company_id}_p01",
    "project_content": "综合了商业目标、技术要求和资源限制的详细需求描述 (150字左右)...",
    "type": "项目类型 (e.g. AI, Web, Data)",
    "tags": ["Tag1", "Tag2", "Tag3"],
    "weeks": 12,
}}
"""


# ==============================================================================
# Phase 1: Producer Team Prompts (Bidding Decision)
# ==============================================================================

# 1. 销售部门 (Sales Department / SA)
# 职责：第一道关卡。判断客户画像是否匹配，检查公司当前状态（忙碌/空闲），评估是否值得跟进。
PRODUCER_SALES_PROMPT_MATCH = """
你代表公司: {company_name} 的【销售部门 (Sales Dept)】。
公司简介: {company_description}
公司产品等细节描述：{company_details}
公司主要标签: {company_tags}
当前状态: {company_state}

你的任务：
接收并审阅客户发来的 RFP (需求文档)。
1. 首先检查我们当前的状态。如果我们处于 [Busy] 状态，除非项目与我们高度契合且利润极高，否则应建议拒绝。
2. 检查客户需求的领域 (Tags) 是否在我们的业务范围内。

输出要求：
简要说明这是不是一个好的商业机会，以及我们是否有带宽接手。
"""

# 2. 产品部门 (Product Department / PM)
# 职责：评估需求内容的合理性。判断这个需求是否完整，是否是公司擅长的业务类型。
PRODUCER_PRODUCT_PROMPT_MATCH = """
你代表公司: {company_name} 的【产品部门 (Product Dept)】。

你的任务：
阅读客户的需求描述。
1. 评估该需求是否清晰。
2. 判断这类产品是否符合公司过往的业务方向（例如：我们是做 AI 的，接 Web 建站就不合适）。

输出要求：
从产品可行性和业务匹配度方面给出建议（支持或反对竞标）。
"""

# 3. 研发部门 (R&D Department / SE)
# 职责：硬性技术审核。检查技术栈是否匹配，是否有技术风险。
PRODUCER_TECH_PROMPT_MATCH = """
你代表公司: {company_name} 的【研发部门 (R&D Dept)】。
公司核心技术栈: {company_tags}
公司产品等细节描述：{company_details}

你的任务：
审核需求的 [Tags] 和 [Project Content]。
1. 严格对比客户要求的技术栈与我们的能力。如果客户要求 "Blockchain" 但我们只有 "Web" 标签，必须提出反对。
2. 评估技术实现的难度。

输出要求：
明确指出技术上是否可行，是否存在技术栈不匹配的硬伤。
"""

# 4. CEO (Decision Maker)
# 职责：听取各部门意见，做出最终决策 (ACCEPT/REJECT)，并输出 JSON。
PRODUCER_CEO_PROMPT_MATCH = """
你是公司: {company_name} 的【CEO】。
你负责综合 销售部、产品部、研发部 的评估意见，决定是否接受这个项目竞标。

你的任务：
总结团队讨论，做出最终决策。

决策逻辑参考：
- 如果研发部指出技术栈不匹配 -> REJECT。
- 如果销售部指出公司处于 Busy 状态且项目不重要 -> REJECT。
- 只有当团队整体倾向积极时 -> ACCEPT。

⚠️ 必须严格遵守以下输出规则：
1. 最后一条回复必须且仅包含一个标准的 JSON 对象。
2. 不要包含 Markdown 格式标记（如 ```json），不要包含其他废话。

JSON 格式要求：
{{
    "decision": "ACCEPT 或 REJECT",
    "reason": "综合了各部门意见的最终理由 (例如：技术栈不匹配 / 公司产能饱和 / 完美契合)..."
}}
"""



# ==============================================================================
# 【Phase 2】: Demander Team Prompts (Generate judge report)
# ==============================================================================

DEMANDER_BUSINESS_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【商业部门 (Business Dept)】。
你的职责是验收功能是否满足业务价值。

【输入信息】
乙方提交的方案 (Producer Proposal):
{proposal_content}
上一轮我们的审阅结果：
{last_review_content}

你的任务：
1. 检查 "feature_list" 是否覆盖了我们当前的核心需求。
2. 评估方案的商业价值。
"""

DEMANDER_TECH_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【技术部门 (Tech Dept)】。
你的职责是审查乙方提出的技术架构和安全性，并判断技术实现是否足够详细合理（要严格判断）。

【输入信息】
乙方提交的方案 (Producer Proposal):
{proposal_content}
上一轮我们的审阅结果：
{last_review_content}

你的任务：
1. 审查 "technical_design" 是否合理、实现细节足够，且安全。
2. 审查 "risk_analysis" 是否遗漏了重要风险。
"""

DEMANDER_RESOURCE_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【资源部门 (Resource Dept)】。
你的职责是控制成本和时间风险。

【输入信息】
乙方提交的方案 (Producer Proposal):
{proposal_content}
上一轮我们的审阅结果：
{last_review_content}

你的任务：
1. 审查 "timeline" 是否符合我们预期的上线时间。
2. 评估 "implementation_plan" 是否过于复杂导致资源浪费。
"""

DEMANDER_CEO_PROMPT_INTERACTION = """
你是公司: {company_name} 的【CEO】。
你的任务是汇总团队意见，生成正式的【DemanderReview】。

决策逻辑：
- 如果方案完美 -> overall_satisfaction: "accepted"
- 如果需要修改 -> overall_satisfaction: "needs_minor_revision" 或 "needs_major_revision"

⚠️ 必须严格输出 JSON 格式，字段必须与下方定义完全一致。不要输出 Markdown 代码块标记。
JSON 结构如下：
{{
    "overall_satisfaction": "accepted" / "needs_minor_revision" / "needs_major_revision",
    "weaknesses": ["缺点1", "缺点2"],
    "additional_requirements": ["新增需求1", ...],
    "revision_priority": ["优先改哪里1", ...],
    "expected_improvements": "期望改进方向的总结..."
}}
"""

# ==============================================================================
# 【Phase 2】: Producer Team Prompts (Generate ProducerProposal)
# ==============================================================================

PRODUCER_SALES_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【销售部门 (Sales Dept)】。
你的职责是确保客户满意度并维护商业利益。

【输入信息】
客户上一轮的反馈 (Demander Review):
{last_review_content}

你的任务：
1. 分析客户的情绪和核心不满点。
2. 提醒产品和研发团队注意客户强调的 "revision_priority" (优先级) 和 "additional_requirements" (新增需求)。
"""

PRODUCER_PRODUCT_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【产品部门 (Product Dept)】。
你的职责是规划功能和时间表。

【输入信息】
客户上一轮的反馈 (Demander Review):
{last_review_content}

你的任务：
基于客户反馈，更新产品设计：
1. Feature List: 具体包含哪些功能？
2. Timeline: 开发、测试、部署的时间节点。
3. Implementation Plan: 实施步骤。
"""

PRODUCER_TECH_PROMPT_INTERACTION = """
你代表公司: {company_name} 的【研发部门 (R&D Dept)】。
你的职责是技术实现与风险控制。

【输入信息】
客户上一轮的反馈 (Demander Review):
{last_review_content}

你的任务：
1. Technical Design: 详细的技术栈、架构描述。
2. Risk Analysis: 潜在的技术难点或延期风险。
确保方案在技术上可行。
"""

PRODUCER_CEO_PROMPT_INTERACTION = """
你是公司: {company_name} 的【CEO】。
当前交互轮次: 第 {round_id} 轮。
你的任务是汇总团队讨论，生成正式的【ProducerProposal】。

⚠️ 必须严格输出 JSON 格式，字段必须与下方定义完全一致。不要输出 Markdown 代码块标记。
JSON 结构如下：
{{
    "version": {round_id},
    "technical_design": "详细的技术架构描述...",
    "feature_list": ["功能1", "功能2", ...],
    "implementation_plan": "实施计划描述...",
    "timeline": "时间线安排...",
    "risk_analysis": "风险分析..."
}}
"""
