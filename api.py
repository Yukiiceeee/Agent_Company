import os
import time
from openai import OpenAI
from openai import AsyncOpenAI
from zai import ZhipuAiClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
import pydantic
import json

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "9ef211babbe74eff8f3c3c609d5a4d68.rDkx1q72bq8VAwZn")

MODEL_INFO = {
    "vision": False,
    "function_calling": True,
    "json_output": False,
    "family": "glm",
    "structured_output": False,
}
MODEL_CLIENT = OpenAIChatCompletionClient(
    model="glm-4.5",
    api_key=ZHIPU_API_KEY,
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model_info=MODEL_INFO,
    max_retries=3,
    timeout=120,
    extra_body={
        "thinking": {
            "type": "disabled",
        },
    }
)
JSON_MODEL_CLIENT = OpenAIChatCompletionClient(
    model="glm-4.5", 
    api_key=ZHIPU_API_KEY,
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model_info={**MODEL_INFO, "json_output": True}, 
    max_retries=3,
    response_format={"type": "json_object"}, 
    extra_body={
        "thinking": {
            "type": "disabled",
        },
    }
)

client = ZhipuAiClient(
    api_key=ZHIPU_API_KEY,
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)
async_client = AsyncOpenAI(
    api_key=ZHIPU_API_KEY,
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    max_retries=5,
    timeout=12
)

def get_schema_prompt(model_class) -> str:
    schema = model_class.model_json_schema()
    return json.dumps(schema, ensure_ascii=False)

def call_glm(user_prompt, schema: object = None, sys_prompt="你是一个商业分析专家。", temperature=0.3, max_tokens=4096):
    try:
        response_format = None
        if schema:
            response_format = {"type": "json_object"}
            sys_prompt += f"\n\n【重要】请严格按照以下 JSON Schema 格式输出结果，不要包含 markdown 标记：\n{get_schema_prompt(schema)}"
        completion = client.chat.completions.create(
            model="glm-4.5",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            thinking={
                "type": "disabled",
            },
            temperature=temperature, 
            max_tokens=max_tokens,
            response_format=response_format
        )
        return completion.choices[0].message.content.strip()

    except Exception as e:
        return f"failed:{str(e)}"
    
async def async_call_glm(user_prompt, schema: object = None, sys_prompt="你是一个商业分析专家。", temperature=0.3, max_tokens=4096):
    try:
        response_format = None
        if schema:
            response_format = {"type": "json_object"}
            sys_prompt += f"\n\n【重要】请严格按照以下 JSON Schema 格式输出结果，不要包含 markdown 标记：\n{get_schema_prompt(schema)}"

        completion = await async_client.chat.completions.create(
            model="GLM-4.5",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature, 
            max_tokens=max_tokens,  
            response_format=response_format,
            extra_body={
                "thinking": {
                    "type": "disabled"
                }
            },
            top_p=0.9,  
        )
        return completion.choices[0].message.content.strip()

    except Exception as e:
        return f"failed:{str(e)}"