from sqlite3.dbapi2 import paramstyle

from pyarrow import output_stream

from app.logger import logger
from app.tool.base import BaseTool, ToolResult
import aiohttp
import asyncio
import json
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class RealityAwareness(BaseTool):
    """Reality Awareness Tool for Manus Agent."""
    name: str = "reality_awareness"
    description: str = """提供当前的时间信息以及对应城市的天气信息。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "(必填) 需要查询天气的城市名",
            }
        },
        "required": ["city"],
    }

    # 高德地图API密钥
    api_key: str = "09335be822a1469e34ce42877c0301d7"

    async def _get_city_code(self, city: str) -> str:
        """
        获取城市编码

        Args:
            city (str): 城市名

        Returns:
            str: 城市编码
        """
        url = "https://restapi.amap.com/v3/config/district"
        params = {
            "key": self.api_key,
            "keywords": city,
            "subdistrict": "0",
            "extensions": "base",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"高德地图城市编码搜索失败: {response.status}")
                        raise ValueError("获取城市编码失败")

                    data = await response.json()

                    if data["status"] != "1" or not data.get("districts"):
                        logger.error(f"城市编码搜索失败: {data}")
                        raise ValueError("获取城市编码失败")

                    # 返回第一个匹配的城市编码
                    return data["districts"][0]["adcode"]
        except Exception as e:
            logger.error(f"获取城市编码时发生异常: {str(e)}")
            raise ValueError("获取城市编码时发生异常")

    async def _get_weather(self, city_code: str) -> str:
        """
        获取天气信息

        Args:
            city_code (str): 城市编码

        Returns:
            str: 格式化后的天气信息字符串
        """
        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city_code,
            "extensions": "all",
            "output": "JSON"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"高德地图天气搜索失败: {response.status}")
                        return "获取天气信息失败"

                    data = await response.json()

                    if data["status"] != "1":
                        logger.error(f"天气搜索失败: {data}")
                        return "获取天气信息失败"

                    # 提取预报信息
                    forecast = data["forecasts"][0]
                    city = forecast["city"]
                    report_time = forecast["reporttime"]
                    casts = forecast["casts"]

                    # 构建天气信息字符串
                    weather_info = f"{city}天气预报（更新于{report_time}）:\n"

                    for cast in casts:
                        weather_info += (
                            f"\n日期: {cast['date']} 星期{cast['week']}\n"
                            f"白天天气: {cast['dayweather']}\n"
                            f"夜间天气: {cast['nightweather']}\n"
                            f"白天温度: {cast['daytemp']}℃\n"
                            f"夜间温度: {cast['nighttemp']}℃\n"
                            f"白天风向: {cast['daywind']}风\n"
                            f"夜间风向: {cast['nightwind']}风\n"
                            f"风力等级: {cast['daypower']}级\n"
                        )

                    return weather_info
        except Exception as e:
            logger.error(f"获取天气信息时发生异常: {str(e)}")
            return "获取天气信息时发生异常"

    async def execute(self, city: str) -> ToolResult:
        """
        获取当前时间和天气信息。

        Args:
            city (str): 城市名

        Returns:
            ToolResult: 包含当前时间和天气信息的结果对象
        """
        try:
            # 获取当前时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 获取城市编码
            city_code = await self._get_city_code(city)

            # 获取天气信息
            weather_info = await self._get_weather(city_code)

            # 返回结果
            result = [
                f"## 已为您查询到时间和天气信息:",
                "",
                f"### 当前时间: {current_time}",
                f"### 天气信息:",
                f"{weather_info}",
            ]
            return ToolResult(output = "\n".join(result))
        except Exception as e:
            logger.error(f"时间天气查询失败: {str(e)}")
            return ToolResult(output=f"查询失败: {str(e)}")