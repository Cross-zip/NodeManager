import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

#用户配置API_KEY和模型，content为请求内容
key = os.getenv("DEEPSEEK_API_KEY")
model = "deepseek-reasoner"
content = "测试，回复1"

#调用API获取响应
def get_response(key,model,content):
    content = "测试，回复1"

    client = OpenAI(
        api_key=key,
        base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个blender5.0版本专家"},
            {"role": "user", "content": content},
        ],
        stream=False
    )

    print(response.choices[0].message.content)