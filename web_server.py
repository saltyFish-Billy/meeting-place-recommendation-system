import asyncio
import os
import sys
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app.agent.manus import Manus
from app.logger import logger
from app.tool.cafe_recommender import CafeRecommender

app = FastAPI(title="OpenManus Web", description="OpenManus咖啡馆推荐Web服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")

# 创建工作目录
os.makedirs("workspace/js_src", exist_ok=True)

# 创建Manus代理
agent = Manus()

class CafeRequest(BaseModel):
    locations: List[str]
    keywords: str = "咖啡馆"
    user_requirements: str = ""

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """主页处理，检测query参数并调用代理处理"""
    # 解析URL获取查询参数
    query_params = parse_qs(urlparse(str(request.url)).query)

    if "query" in query_params and query_params["query"]:
        # 获取查询参数
        query = query_params["query"][0]

        try:
            # 执行查询
            logger.info(f"处理查询: {query}")
            result = await agent.run(user_query=query)

            # 构建HTML显示结果
            # 使用replace处理换行符
            formatted_result = result.replace('\n', '<br>')

            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>OpenManus - 咖啡馆查找结果</title>
                <style>
                    body {{
                        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 0;
                        color: #333;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        max-width: 1000px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    header {{
                        background-color: #2c3e50;
                        color: white;
                        padding: 20px 0;
                        text-align: center;
                        margin-bottom: 30px;
                        border-radius: 5px;
                    }}
                    .content-section {{
                        background-color: white;
                        border-radius: 5px;
                        padding: 20px;
                        margin-bottom: 30px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    }}
                    .back-link {{
                        display: inline-block;
                        margin-top: 20px;
                        color: #2c3e50;
                        text-decoration: none;
                    }}
                    .back-link:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <header>
                        <h1>咖啡馆查找结果</h1>
                    </header>
                    <div class="content-section">
                        <div class="result-content">
                            {formatted_result}
                        </div>
                        <a href="/workspace/cafe_finder.html" class="back-link">← 返回查找页面</a>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        except Exception as e:
            # 错误处理
            error_message = f"处理查询时出错: {str(e)}"
            logger.error(error_message)

            error_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>错误</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    .error { color: red; }
                </style>
            </head>
            <body>
                <h1>处理请求时出错</h1>
                <p class="error">""" + error_message + """</p>
                <a href="/workspace/cafe_finder.html">返回查找页面</a>
            </body>
            </html>
            """
            return HTMLResponse(content=error_html)

    # 如果没有查询参数，重定向到咖啡馆查找页面
    return RedirectResponse(url="/workspace/cafe_finder.html")

@app.post("/api/find_cafe")
async def find_cafe(request: CafeRequest):
    # 创建推荐器实例
    recommender = CafeRecommender()

    # 执行推荐
    result = await recommender.execute(
        locations=request.locations,
        keywords=request.keywords,
        user_requirements=request.user_requirements
    )

    # 从结果中提取HTML文件路径
    output_text = result.output
    html_path = None

    for line in output_text.split('\n'):
        if "HTML页面:" in line:
            html_path = line.split("HTML页面:")[1].strip()
            # 清理路径中的引号
            html_path = html_path.replace('"', '').replace("'", '')
            break

    if not html_path:
        return "无法生成HTML页面"

    # 返回生成的HTML页面URL，确保路径格式正确且没有多余的引号
    return f"/workspace/js_src/{html_path}"

if __name__ == "__main__":
    # 启动Web服务器
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
