import json
import os
import time
import re
import traceback
import asyncio
import argparse
from typing import List, Dict, Any
from configs.roles import *
from configs.prompts import INIT_PROMPT
from configs.prompts import REFRESH_PROMPT
from api import call_glm
from api import async_call_glm
from utils import extract_json

CONCURRENCY_LIMIT = 5

async def async_create_company_instance(info, semaphore):
    async with semaphore:
        company_id = info.get('id', '0')
        name = info.get('公司名称', info.get('name', '未命名公司'))
        description = info.get('公司介绍', info.get('description', '暂无介绍'))
        details = info.get('产品服务', info.get('product', ''))
        # news = info.get('新闻资讯', info.get('history', ''))

        init_info = {
            "company_id": company_id,
            "name": name,
            "description": description,
            "details": details,
        }
        prompt = INIT_PROMPT.format(**init_info)
        
        try:
            print(f"⏳ 开始生成: {name}...") 
            llm_response = await async_call_glm(prompt, schema=CompanyInfo)
            print(f"🤖 LLM 回答: {llm_response}")
            
            ai_data = extract_json(llm_response)
            
            if not ai_data:
                raise ValueError("LLM 返回无法解析为 JSON")

            tags = ai_data.get("tags", [])
            strategy_content = ai_data.get("strategy_content", "")
            current_role_str = ai_data.get("current_role", "Producer")

            # 所有企业都生成战略规划
            if not strategy_content:
                strategy_content = "企业发展与技术合作规划。"
            strategy = StrategicPlan(content=strategy_content)

            # 根据current_role判断当前轮次的角色
            if "Demander" in current_role_str:
                role = CompanyRole.DEMANDER
            else:
                role = CompanyRole.PRODUCER 

            company = Company(
                company_id=str(company_id),
                name=name,
                role=role,
                description=description,
                details=details,
                tags=tags,
                strategy=strategy,
                state=CompanyState.IDLE
            )
            
            print(f" [完成] {name} -> Role: {role.value}")
            return company
        
        except Exception as e:
            print(f" [失败] {name}")
            print(f"❌ Error initializing {name}: {e}")
            # traceback.print_exc()
            return None
    
async def async_create_companies_list(data_path: str) -> List[Company]:
    all_companies = []

    if os.path.exists(data_path):
        print(f"📂 读取数据文件: {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
            
        print(f"📊 共加载 {len(raw_list)} 条原始数据，开始并发初始化 (并发数: {CONCURRENCY_LIMIT})...\n")
        
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        
        tasks = []
        for company_info in raw_list:
            task = async_create_company_instance(info=company_info, semaphore=semaphore)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        all_companies = [r for r in results if r is not None]
        
        print(f"\n✅ 初始化完成! 成功生成 {len(all_companies)} 个企业 Agent。")
    else:
        print(f"❌ 文件导入失败: {data_path}")

    return all_companies

async def async_refresh_company_instance(company: Company, current_week: int, semaphore):
    async with semaphore:
        if not company.is_idle(current_week):
            return company

        history_text = "\n".join(company.project_history[-3:]) if company.project_history else "暂无近期项目历史。"
        
        prompt = REFRESH_PROMPT.format(
            name=company.name,
            current_week=current_week,
            description=company.description,
            last_role=company.role.value,
            history_summary=history_text
        )

        try:
            llm_response = await async_call_glm(prompt, schema=CompanyRefreshInfo)
            ai_data = extract_json(llm_response)

            if ai_data:
                new_strategy = ai_data.get("strategy_content", company.strategy.content)
                company.strategy = StrategicPlan(content=new_strategy)
                role_str = ai_data.get("current_role", "Producer")
                if "Demander" in role_str:
                    company.role = CompanyRole.DEMANDER
                else:
                    company.role = CompanyRole.PRODUCER
                company.state = CompanyState.IDLE
                
            return company

        except Exception as e:
            print(f"⚠️ 刷新失败 {company.name}: {e}")
            return company

async def async_refresh_companies_list(companies: List[Company], current_week: int) -> List[Company]:
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []

    target_companies = [c for c in companies if c.is_idle(current_week)]
    print(f"🔄 [Week {current_week}] Refreshing strategies for {len(target_companies)} idle companies...")

    for company in target_companies:
        task = async_refresh_company_instance(company, current_week, semaphore)
        tasks.append(task)
    if tasks:
        await asyncio.gather(*tasks)

    return companies


# def create_company_instance(info):
#     company_id = info.get('id', '0')
#     name = info.get('公司名称', info.get('name', '未命名公司'))
#     description = info.get('公司介绍', info.get('description', '暂无介绍'))
#     details = info.get('产品服务', info.get('product', ''))
#     news = info.get('新闻资讯', info.get('history', ''))

#     init_info = {
#         "company_id": company_id,
#         "name": name,
#         "description": description,
#         "details": details,
#     }
#     prompt = INIT_PROMPT.format(**init_info)
    
#     try:
#         llm_response = call_glm(prompt, schema=CompanyInfo)
#         print(f"🤖 LLM 回答: {llm_response}")
        
#         ai_data = extract_json(llm_response)
        
#         if not ai_data:
#             raise ValueError("LLM 返回无法解析为 JSON")

#         tags = ai_data.get("tags", [])
#         strategy_content = ai_data.get("strategy_content", "")
#         current_role_str = ai_data.get("current_role", "Producer")

#         # 所有企业都生成战略规划
#         if not strategy_content:
#             strategy_content = "企业发展与技术合作规划。"
#         strategy = StrategicPlan(content=strategy_content)

#         # 根据current_role判断当前轮次的角色
#         if "Demander" in current_role_str:
#             role = CompanyRole.DEMANDER
#         else:
#             role = CompanyRole.PRODUCER 

#         company = Company(
#             company_id=str(company_id),
#             name=name,
#             role=role,
#             description=description,
#             details=details,
#             tags=tags,
#             strategy=strategy,
#             state=CompanyState.IDLE
#         )
        
#         print(f" [完成] -> Role: {role.value}")
#         return company
    
#     except Exception as e:
#         print(f" [失败]")
#         print(f"❌ Error initializing {name}: {e}")
#         traceback.print_exc()
#         return None
    
# def create_companies_list(data_path: str) -> List[Company]:

#     all_companies = []

#     if os.path.exists(data_path):
#         print(f"📂 读取数据文件: {data_path}")
#         with open(data_path, "r", encoding="utf-8") as f:
#             raw_list = json.load(f)
            
#         print(f"📊 共加载 {len(raw_list)} 条原始数据，开始初始化...\n")
        
#         for company_info in raw_list:
#             company = create_company_instance(info=company_info)
#             if company:
#                 all_companies.append(company)
        
#         print(f"\n✅ 初始化完成! 成功生成 {len(all_companies)} 个企业 Agent。")
#     else:
#         print(f"❌ 文件导入失败: {data_path}")

#     return all_companies

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path', type=str, default="../data/companies_info.json", help='Path to the companies_info.json file')
    args = parser.parse_args()

    data_path = args.data_path

    start_time = time.time()

    # all_companies = create_companies_list(data_path=data_path)
    all_companies = asyncio.run(async_create_companies_list(data_path=data_path))

    end_time = time.time()
    elapsed_time = end_time - start_time

    print("\n" + "="*50)
    print(f"⏱️  执行耗时统计:")
    print(f"    总耗时  : {elapsed_time:.2f} 秒")
    if len(all_companies) > 0:
        print(f"    平均耗时: {elapsed_time / len(all_companies):.2f} 秒/个")
    print("="*50 + "\n")

    print("\n[Preview Data]:")
    for idx, c in enumerate(all_companies):
        s_content = c.strategy.content if c.strategy else "None"
        print(f"{idx+1}. [{c.role.value}] {c.name} | Tags: {c.tags} | Strategy: {s_content[:30]}...")