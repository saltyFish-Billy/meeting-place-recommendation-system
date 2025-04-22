import asyncio
import json
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import aiohttp
from pydantic import Field

from app.logger import logger
from app.tool.base import BaseTool, ToolResult




class CafeRecommender(BaseTool):
    """咖啡馆推荐工具，基于多个地点计算最佳会面位置并推荐咖啡馆"""

    name: str = "cafe_recommender"
    description: str = """推荐适合多人会面的咖啡馆。
该工具基于多个地点的位置信息，计算最佳会面地点，并推荐附近的咖啡馆。
工具会生成包含地图和推荐信息的HTML页面，提供详细的店铺信息、地理位置和交通建议。
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "locations": {
                "type": "array",
                "description": "(必填) 所有参与者的位置描述列表，每个元素为一个地点描述字符串，如['北京朝阳区望京宝星园', '海淀中关村地铁站']",
                "items": {"type": "string"},
            },
            "keywords": {
                "type": "string",
                "description": "(可选) 搜索关键词，默认为'咖啡馆'",
                "default": "咖啡馆",
            },
            "user_requirements": {
                "type": "string",
                "description": "(可选) 用户的额外需求，如'停车方便'，'环境安静'等",
                "default": "",
            },
        },
        "required": ["locations"],
    }

    # 高德地图API密钥
    api_key: str = "09335be822a1469e34ce42877c0301d7"

    # 缓存请求结果以减少API调用
    geocode_cache: Dict[str, Dict] = Field(default_factory=dict)
    poi_cache: Dict[str, List] = Field(default_factory=dict)

    async def execute(
        self,
        locations: List[str],
        keywords: str = "咖啡馆",
        user_requirements: str = "",
    ) -> ToolResult:
        """
        执行咖啡馆推荐

        Args:
            locations: 多个地点描述的列表
            keywords: 搜索关键词，默认为"咖啡馆"
            user_requirements: 用户的额外需求

        Returns:
            ToolResult: 包含推荐结果和生成的HTML页面路径
        """
        try:
            # 1. 获取每个地点的坐标
            coordinates = []
            location_info = []

            for location in locations:
                geocode_result = await self._geocode(location)
                if not geocode_result:
                    return ToolResult(output=f"无法找到地点: {location}")

                # 提取坐标
                lng, lat = geocode_result["location"].split(",")
                coordinates.append((float(lng), float(lat)))

                # 保存地点信息
                location_info.append({
                    "name": location,
                    "formatted_address": geocode_result.get("formatted_address", location),
                    "location": geocode_result["location"],
                    "lng": float(lng),
                    "lat": float(lat)
                })

            # 2. 计算中心点
            center_point = self._calculate_center_point(coordinates)

            # 3. 搜索中心点附近的咖啡馆
            cafes = await self._search_pois(
                f"{center_point[0]},{center_point[1]}",
                keywords,
                radius=2000  # 2公里范围内
            )

            if not cafes:
                return ToolResult(output=f"在计算的中心点附近找不到{keywords}")

            # 4. 根据评分、距离等因素筛选和排序咖啡馆
            recommended_cafes = self._rank_cafes(cafes, center_point, user_requirements)

            # 5. 生成HTML页面
            html_path = await self._generate_html_page(
                location_info,
                recommended_cafes,
                center_point,
                user_requirements
            )

            # 6. 构建返回结果
            result_text = self._format_result_text(location_info, recommended_cafes, html_path)

            return ToolResult(output=result_text)

        except Exception as e:
            logger.error(f"咖啡馆推荐失败: {str(e)}")
            return ToolResult(output=f"推荐失败: {str(e)}")

    async def _geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """通过高德地图API获取地址的经纬度"""
        # 如果缓存中存在，直接返回
        if address in self.geocode_cache:
            return self.geocode_cache[address]

        url = "https://restapi.amap.com/v3/geocode/geo"
        params = {
            "key": self.api_key,
            "address": address,
            "output": "json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"高德地图API请求失败: {response.status}")
                    return None

                data = await response.json()

                if data["status"] != "1" or not data["geocodes"]:
                    logger.error(f"地理编码失败: {data}")
                    return None

                result = data["geocodes"][0]
                self.geocode_cache[address] = result
                return result

    def _calculate_center_point(self, coordinates: List[Tuple[float, float]]) -> Tuple[float, float]:
        """计算多个坐标的几何中心点"""
        if not coordinates:
            raise ValueError("至少需要一个坐标")

        # 简单的算术平均
        avg_lng = sum(lng for lng, _ in coordinates) / len(coordinates)
        avg_lat = sum(lat for _, lat in coordinates) / len(coordinates)

        return (avg_lng, avg_lat)

    async def _search_pois(
        self,
        location: str,
        keywords: str,
        radius: int = 2000,
        types: str = "050000",  # 餐饮类POI
        offset: int = 20
    ) -> List[Dict]:
        """搜索兴趣点"""
        cache_key = f"{location}_{keywords}_{radius}_{types}"
        if cache_key in self.poi_cache:
            return self.poi_cache[cache_key]

        url = "https://restapi.amap.com/v3/place/around"
        params = {
            "key": self.api_key,
            "location": location,
            "keywords": keywords,
            "types": types,
            "radius": radius,
            "offset": offset,
            "page": 1,
            "extensions": "all"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"高德地图POI搜索失败: {response.status}")
                    return []

                data = await response.json()

                if data["status"] != "1":
                    logger.error(f"POI搜索失败: {data}")
                    return []

                pois = data.get("pois", [])
                self.poi_cache[cache_key] = pois
                return pois

    def _rank_cafes(
        self,
        cafes: List[Dict],
        center_point: Tuple[float, float],
        user_requirements: str
    ) -> List[Dict]:
        """根据多种因素对咖啡馆进行排序"""
        # 提取用户需求关键词
        requirement_keywords = {
            "停车": ["停车", "车位", "停车场"],
            "安静": ["安静", "环境好", "氛围"],
            "商务": ["商务", "会议", "办公"],
            "交通": ["交通", "地铁", "公交"]
        }

        user_priorities = []
        for key, keywords in requirement_keywords.items():
            if any(kw in user_requirements for kw in keywords):
                user_priorities.append(key)

        # 为每个咖啡馆计算综合分数
        for cafe in cafes:
            score = 0

            # 基础分 - 评分 (0-5分)
            rating = float(cafe.get("biz_ext", {}).get("rating", "0") or "0")
            score += rating * 10  # 0-50分

            # 距离分 - 距离中心点越近越好 (0-20分)
            cafe_lng, cafe_lat = cafe["location"].split(",")
            distance = self._calculate_distance(
                center_point,
                (float(cafe_lng), float(cafe_lat))
            )
            # 距离在1公里内得20分，超过2公里得0分，线性衰减
            distance_score = max(0, 20 * (1 - (distance / 2000)))
            score += distance_score

            # 用户需求加分 (每项最多10分)
            for priority in user_priorities:
                if priority == "停车" and ("停车" in cafe.get("tag", "") or "免费停车" in cafe.get("business", "")):
                    score += 10
                elif priority == "安静" and ("环境" in cafe.get("tag", "") or "安静" in cafe.get("tag", "")):
                    score += 10
                elif priority == "商务" and ("商务" in cafe.get("tag", "") or "会议" in cafe.get("business", "")):
                    score += 10
                elif priority == "交通" and ("地铁" in cafe.get("tag", "") or "公交" in cafe.get("business", "")):
                    score += 10

            # 保存分数
            cafe["_score"] = score

        # 按分数排序
        ranked_cafes = sorted(cafes, key=lambda x: x.get("_score", 0), reverse=True)

        # 返回前5个结果
        return ranked_cafes[:5]

    def _calculate_distance(
        self,
        point1: Tuple[float, float],
        point2: Tuple[float, float]
    ) -> float:
        """计算两点之间的距离（米）"""
        # 使用简化的平面距离计算（对于城市内小范围足够精确）
        # 1经度约为85km，1纬度约为111km（在中国地区）
        lng1, lat1 = point1
        lng2, lat2 = point2

        # 将经纬度转换为距离（米）
        x = (lng2 - lng1) * 85000
        y = (lat2 - lat1) * 111000

        return math.sqrt(x*x + y*y)

    async def _generate_html_page(
        self,
        locations: List[Dict],
        cafes: List[Dict],
        center_point: Tuple[float, float],
        user_requirements: str
    ) -> str:
        """生成HTML页面并返回文件路径"""
        # 生成HTML内容
        html_content = self._generate_html_content(locations, cafes, center_point, user_requirements)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_name = f"cafe_recommendation_{timestamp}_{unique_id}.html"

        # 确保目录存在
        os.makedirs("workspace/js_src", exist_ok=True)
        file_path = f"workspace/js_src/{file_name}"

        # 写入文件
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(html_content)

        return file_path

    def _generate_html_content(
        self,
        locations: List[Dict],
        cafes: List[Dict],
        center_point: Tuple[float, float],
        user_requirements: str
    ) -> str:
        """生成HTML页面内容"""
        # 生成搜索过程步骤HTML
        search_process_html = self._generate_search_process(locations, center_point, user_requirements)

        # 生成位置标记数据
        location_markers = []
        for idx, loc in enumerate(locations):
            location_markers.append({
                "name": f"地点{idx+1}: {loc['name']}",
                "position": [loc["lng"], loc["lat"]],
                "icon": "location"
            })

        # 生成咖啡馆标记数据
        cafe_markers = []
        for cafe in cafes:
            lng, lat = cafe["location"].split(",")
            cafe_markers.append({
                "name": cafe["name"],
                "position": [float(lng), float(lat)],
                "icon": "cafe"
            })

        # 中心点标记
        center_marker = {
            "name": "最佳会面点",
            "position": [center_point[0], center_point[1]],
            "icon": "center"
        }

        # 所有标记点
        all_markers = [center_marker] + location_markers + cafe_markers

        # 生成地点行HTML
        location_rows_html = ""
        for idx, loc in enumerate(locations):
            location_rows_html += f"<tr><td>{idx+1}</td><td>{loc['name']}</td><td>{loc['formatted_address']}</td></tr>"

        # 生成位置距离列表HTML
        location_distance_html = ""
        for loc in locations:
            distance = self._calculate_distance(center_point, (loc['lng'], loc['lat']))/1000
            location_distance_html += f"<li><i class='bx bx-map'></i><strong>{loc['name']}</strong>: 距离中心点约 <span class='distance'>{distance:.1f} 公里</span></li>"

        # 生成咖啡馆卡片HTML
        cafe_cards_html = ""
        for cafe in cafes:
            # 提取评分
            rating = cafe.get("biz_ext", {}).get("rating", "暂无评分")

            # 提取地址
            address = cafe.get("address", "地址未知")

            # 提取营业时间
            business_hours = cafe.get("business_hours", "营业时间未知")
            if isinstance(business_hours, list) and business_hours:
                business_hours = "; ".join(business_hours)

            # 提取电话
            tel = cafe.get("tel", "电话未知")

            # 提取标签
            tags = cafe.get("tag", [])
            if isinstance(tags, str):
                tags = tags.split(";")
            elif not isinstance(tags, list):
                tags = []

            tags_html = ""
            for tag in tags:
                if tag.strip():
                    tags_html += f"<span class='cafe-tag'>{tag.strip()}</span>"

            if not tags_html:
                tags_html = "<span class='cafe-tag'>咖啡馆</span>"

            # 计算到中心点的距离
            lng, lat = cafe["location"].split(",")
            distance = self._calculate_distance(
                center_point,
                (float(lng), float(lat))
            )
            distance_text = f"{distance/1000:.1f} 公里"

            # 生成咖啡馆卡片HTML
            cafe_cards_html += f'''
            <div class="cafe-card">
                <div class="cafe-img">
                    <i class='bx bxs-coffee-alt'></i>
                </div>
                <div class="cafe-content">
                    <div class="cafe-header">
                        <div>
                            <h3 class="cafe-name">{cafe['name']}</h3>
                        </div>
                        <span class="cafe-rating">评分: {rating}</span>
                    </div>
                    <div class="cafe-details">
                        <div class="cafe-info">
                            <i class='bx bx-map'></i>
                            <div class="cafe-info-text">{address}</div>
                        </div>
                        <div class="cafe-info">
                            <i class='bx bx-time'></i>
                            <div class="cafe-info-text">{business_hours}</div>
                        </div>
                        <div class="cafe-info">
                            <i class='bx bx-phone'></i>
                            <div class="cafe-info-text">{tel}</div>
                        </div>
                        <div class="cafe-tags">
                            {tags_html}
                        </div>
                    </div>
                    <div class="cafe-footer">
                        <div class="cafe-distance">
                            <i class='bx bx-walk'></i> {distance_text}
                        </div>
                        <div class="cafe-actions">
                            <a href="https://uri.amap.com/marker?position={lng},{lat}&name={cafe['name']}" target="_blank">
                                <i class='bx bx-navigation'></i>导航
                            </a>
                        </div>
                    </div>
                </div>
            </div>'''

        # 生成JavaScript对象
        markers_json = json.dumps(all_markers)

        # 定义HTML基础部分
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>咖啡会 - 最佳会面咖啡馆推荐</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/boxicons@2.0.9/css/boxicons.min.css">
    <style>
        :root {{
            --primary: #9c6644;
            --primary-light: #c68b59;
            --primary-dark: #7f5539;
            --secondary: #c9ada7;
            --light: #f2e9e4;
            --dark: #22223b;
            --success: #4a934a;
            --border-radius: 12px;
            --box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
            --transition: all 0.3s ease;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            background-color: var(--light);
            color: var(--dark);
            padding-bottom: 50px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }}

        header {{
            background-color: var(--primary);
            color: white;
            padding: 60px 0 100px;
            text-align: center;
            position: relative;
            margin-bottom: 80px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        }}

        header::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 60px;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 60"><path fill="%23f2e9e4" fill-opacity="1" d="M0,32L80,42.7C160,53,320,75,480,64C640,53,800,11,960,5.3C1120,0,1280,32,1360,48L1440,64L1440,100L1360,100C1280,100,1120,100,960,100C800,100,640,100,480,100C320,100,160,100,80,100L0,100Z"></path></svg>');
            background-size: cover;
            background-position: center;
        }}

        .header-logo {{
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }}

        .coffee-icon {{
            font-size: 3rem;
            vertical-align: middle;
            margin-right: 10px;
        }}

        .header-subtitle {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}

        .main-content {{
            margin-top: -60px;
        }}

        .card {{
            background-color: white;
            border-radius: var(--border-radius);
            padding: 30px;
            box-shadow: var(--box-shadow);
            margin-bottom: 30px;
            transition: var(--transition);
        }}

        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
        }}

        .section-title {{
            font-size: 1.8rem;
            color: var(--primary-dark);
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--secondary);
            display: flex;
            align-items: center;
        }}

        .section-title i {{
            margin-right: 12px;
            font-size: 1.6rem;
            color: var(--primary);
        }}

        .summary-card {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 15px;
        }}

        .summary-item {{
            flex: 1;
            min-width: 200px;
            padding: 15px;
            background-color: rgba(156, 102, 68, 0.05);
            border-radius: 8px;
            border-left: 4px solid var(--primary);
        }}

        .summary-label {{
            font-size: 0.9rem;
            color: var(--primary-dark);
            margin-bottom: 5px;
        }}

        .summary-value {{
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--dark);
        }}

        .map-container {{
            height: 500px;
            border-radius: var(--border-radius);
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            position: relative;
            margin-bottom: 30px;
        }}

        #map {{
            height: 100%;
            width: 100%;
        }}

        .map-legend {{
            position: absolute;
            bottom: 15px;
            left: 15px;
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
            z-index: 100;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            margin-right: 10px;
            border-radius: 50%;
        }}

        .legend-center {{
            background-color: #2ecc71;
        }}

        .legend-location {{
            background-color: #3498db;
        }}

        .legend-cafe {{
            background-color: #e74c3c;
        }}

        .location-table {{
            width: 100%;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 25px;
            box-shadow: 0 0 8px rgba(0, 0, 0, 0.1);
        }}

        .location-table th, .location-table td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}

        .location-table th {{
            background-color: var(--primary-light);
            color: white;
            font-weight: 600;
        }}

        .location-table tr:last-child td {{
            border-bottom: none;
        }}

        .location-table tr:nth-child(even) {{
            background-color: rgba(201, 173, 167, 0.1);
        }}

        .cafe-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }}

        .cafe-card {{
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
            transition: var(--transition);
            display: flex;
            flex-direction: column;
        }}

        .cafe-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
        }}

        .cafe-img {{
            height: 180px;
            background-color: var(--primary-light);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 3rem;
        }}

        .cafe-content {{
            padding: 20px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}

        .cafe-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}

        .cafe-name {{
            font-size: 1.3rem;
            margin: 0 0 5px 0;
            color: var(--primary-dark);
        }}

        .cafe-rating {{
            display: inline-block;
            background-color: var(--primary);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
            white-space: nowrap;
        }}

        .cafe-details {{
            flex: 1;
        }}

        .cafe-info {{
            margin-bottom: 12px;
            display: flex;
            align-items: flex-start;
        }}

        .cafe-info i {{
            color: var(--primary);
            margin-right: 8px;
            font-size: 1.1rem;
            min-width: 20px;
            margin-top: 3px;
        }}

        .cafe-info-text {{
            flex: 1;
        }}

        .cafe-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 15px;
        }}

        .cafe-tag {{
            background-color: rgba(156, 102, 68, 0.1);
            color: var(--primary-dark);
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
        }}

        .cafe-footer {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }}

        .cafe-distance {{
            display: flex;
            align-items: center;
            color: var(--primary-dark);
            font-weight: 600;
        }}

        .cafe-distance i {{
            margin-right: 5px;
        }}

        .cafe-actions a {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background-color: var(--primary);
            color: white;
            padding: 8px 15px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9rem;
            transition: var(--transition);
        }}

        .cafe-actions a:hover {{
            background-color: var(--primary-dark);
            transform: translateY(-2px);
        }}

        .cafe-actions i {{
            margin-right: 5px;
        }}

        .transportation-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }}

        .transport-card {{
            background-color: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border-top: 5px solid var(--primary);
        }}

        .transport-title {{
            font-size: 1.3rem;
            color: var(--primary-dark);
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }}

        .transport-title i {{
            margin-right: 10px;
            font-size: 1.4rem;
            color: var(--primary);
        }}

        .transport-list {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}

        .transport-list li {{
            padding: 10px 0;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
        }}

        .transport-list li:last-child {{
            border-bottom: none;
        }}

        .transport-list i {{
            color: var(--primary);
            margin-right: 10px;
        }}

        .center-coords {{
            display: inline-block;
            background-color: rgba(156, 102, 68, 0.1);
            border-radius: 6px;
            padding: 3px 8px;
            margin: 0 5px;
            font-family: monospace;
            font-size: 0.9rem;
        }}

        .footer {{
            text-align: center;
            background-color: var(--primary-dark);
            color: white;
            padding: 20px 0;
            margin-top: 50px;
        }}

        .back-button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background-color: white;
            color: var(--primary);
            border: 2px solid var(--primary);
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1rem;
            transition: var(--transition);
            margin-top: 30px;
        }}

        .back-button:hover {{
            background-color: var(--primary);
            color: white;
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}

        .back-button i {{
            margin-right: 8px;
        }}

        /* 搜索过程的样式 */
        .search-process-card {{
            position: relative;
            overflow: hidden;
            background-color: #fafafa;
            border-left: 5px solid #2c3e50;
        }}

        .search-process {{
            position: relative;
            padding: 20px 0;
        }}

        .process-step {{
            display: flex;
            margin-bottom: 30px;
            opacity: 0.5;
            transform: translateX(-20px);
            transition: opacity 0.5s ease, transform 0.5s ease;
        }}

        .process-step.active {{
            opacity: 1;
            transform: translateX(0);
        }}

        .step-icon {{
            flex: 0 0 60px;
            height: 60px;
            border-radius: 50%;
            background-color: var(--primary-light);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
            margin-right: 20px;
            position: relative;
        }}

        .step-number {{
            position: absolute;
            top: -5px;
            right: -5px;
            width: 25px;
            height: 25px;
            border-radius: 50%;
            background-color: var(--primary-dark);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: bold;
        }}

        .step-content {{
            flex: 1;
        }}

        .step-title {{
            font-size: 1.3rem;
            color: var(--primary-dark);
            margin-bottom: 10px;
        }}

        .step-details {{
            background-color: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        }}

        .code-block {{
            background-color: #2c3e50;
            color: #e6e6e6;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9rem;
            margin: 15px 0;
            white-space: pre;
            overflow-x: auto;
        }}

        .highlight-text {{
            background-color: rgba(46, 204, 113, 0.2);
            color: #2c3e50;
            padding: 3px 6px;
            border-radius: 4px;
            font-weight: bold;
        }}

        .search-animation {{
            height: 200px;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 20px 0;
        }}

        .radar-circle {{
            position: absolute;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background-color: rgba(52, 152, 219, 0.1);
            animation: radar 3s infinite;
        }}

        .radar-circle:nth-child(1) {{
            animation-delay: 0s;
        }}

        .radar-circle:nth-child(2) {{
            animation-delay: 1s;
        }}

        .radar-circle:nth-child(3) {{
            animation-delay: 2s;
        }}

        .center-point {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background-color: #e74c3c;
            z-index: 2;
            box-shadow: 0 0 0 5px rgba(231, 76, 60, 0.3);
        }}

        /* 高德地图操作动画 */
        .map-operation-animation {{
            height: 200px;
            position: relative;
            border-radius: 8px;
            overflow: hidden;
            background-color: #f5f5f5;
            margin: 20px 0;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }}

        .map-bg {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="%23f0f0f0"/><path d="M0,0 L100,0 L100,100 L0,100 Z" fill="none" stroke="%23ccc" stroke-width="0.5"/><path d="M50,0 L50,100 M0,50 L100,50" stroke="%23ccc" stroke-width="0.5"/></svg>');
            background-size: 50px 50px;
            opacity: 0.7;
        }}

        .map-cursor {{
            position: absolute;
            width: 20px;
            height: 20px;
            background-color: rgba(231, 76, 60, 0.7);
            border-radius: 50%;
            top: 50%;
            left: 30%;
            transform: translate(-50%, -50%);
            animation: mapCursor 4s infinite ease-in-out;
            z-index: 2;
        }}

        .map-search-indicator {{
            position: absolute;
            width: 80px;
            height: 80px;
            border: 2px dashed rgba(52, 152, 219, 0.6);
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            animation: mapSearch 3s infinite ease-in-out;
            z-index: 1;
        }}

        @keyframes mapCursor {{
            0% {{ left: 30%; top: 30%; }}
            30% {{ left: 60%; top: 40%; }}
            60% {{ left: 40%; top: 70%; }}
            100% {{ left: 30%; top: 30%; }}
        }}

        @keyframes mapSearch {{
            0% {{ width: 30px; height: 30px; opacity: 1; }}
            100% {{ width: 150px; height: 150px; opacity: 0; }}
        }}

        @keyframes radar {{
            0% {{
                width: 40px;
                height: 40px;
                opacity: 1;
            }}
            100% {{
                width: 300px;
                height: 300px;
                opacity: 0;
            }}
        }}

        .ranking-result {{
            margin-top: 15px;
        }}

        .result-bar {{
            height: 30px;
            background-color: var(--primary);
            color: white;
            margin-bottom: 8px;
            border-radius: 15px;
            padding: 0 15px;
            display: flex;
            align-items: center;
            font-weight: 600;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            animation: growBar 2s ease;
            transform-origin: left;
        }}

        @keyframes growBar {{
            0% {{ width: 0; }}
            100% {{ width: 100%; }}
        }}

        .mt-4 {{
            margin-top: 1rem;
        }}

        /* 添加响应式设计 */
        @media (max-width: 768px) {{
            .cafe-grid {{
                grid-template-columns: 1fr;
            }}

            .transportation-info {{
                grid-template-columns: 1fr;
            }}

            header {{
                padding: 40px 0 80px;
            }}

            .header-logo {{
                font-size: 2.2rem;
            }}

            .process-step {{
                flex-direction: column;
            }}

            .step-icon {{
                margin-bottom: 15px;
                margin-right: 0;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-logo">
                <i class='bx bxs-coffee-togo coffee-icon'></i>咖啡会
            </div>
            <div class="header-subtitle">为您找到的最佳会面咖啡馆</div>
        </div>
    </header>

    <div class="container main-content">
        <div class="card">
            <h2 class="section-title"><i class='bx bx-info-circle'></i>推荐摘要</h2>
            <div class="summary-card">
                <div class="summary-item">
                    <div class="summary-label">参与地点数</div>
                    <div class="summary-value">{len(locations)} 个地点</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">推荐咖啡馆数</div>
                    <div class="summary-value">{len(cafes)} 家咖啡馆</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">特殊需求</div>
                    <div class="summary-value">{user_requirements or "无特殊需求"}</div>
                </div>
            </div>
        </div>

        <!-- 在此处添加搜索过程 -->
        {search_process_html}

        <div class="card">
            <h2 class="section-title"><i class='bx bx-map-pin'></i>地点信息</h2>
            <table class="location-table">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>地点名称</th>
                        <th>详细地址</th>
                    </tr>
                </thead>
                <tbody>
                    {location_rows_html}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2 class="section-title"><i class='bx bx-map-alt'></i>地图展示</h2>
            <div class="map-container">
                <div id="map"></div>
                <div class="map-legend">
                    <div class="legend-item">
                        <div class="legend-color legend-center"></div>
                        <span>最佳会面点</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color legend-location"></div>
                        <span>所在地点</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color legend-cafe"></div>
                        <span>咖啡馆</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="section-title"><i class='bx bx-coffee'></i>推荐咖啡馆</h2>
            <div class="cafe-grid">
                {cafe_cards_html}
            </div>
        </div>

        <div class="card">
            <h2 class="section-title"><i class='bx bx-car'></i>交通与停车建议</h2>
            <div class="transportation-info">
                <div class="transport-card">
                    <h3 class="transport-title"><i class='bx bx-trip'></i>前往方式</h3>
                    <p>最佳会面点位于<span class="center-coords">{center_point[0]:.6f}, {center_point[1]:.6f}</span>附近</p>
                    <ul class="transport-list">
                        {location_distance_html}
                    </ul>
                </div>
                <div class="transport-card">
                    <h3 class="transport-title"><i class='bx bxs-car-garage'></i>停车建议</h3>
                    <ul class="transport-list">
                        <li><i class='bx bx-check'></i>大部分推荐的咖啡馆周边有停车场或提供停车服务</li>
                        <li><i class='bx bx-check'></i>建议使用高德地图或百度地图导航到目的地</li>
                        <li><i class='bx bx-check'></i>高峰时段建议提前30分钟出发，以便寻找停车位</li>
                        <li><i class='bx bx-check'></i>部分咖啡馆可能提供免费停车或停车优惠</li>
                    </ul>
                </div>
            </div>

            <a href="/workspace/cafe_finder.html" class="back-button">
                <i class='bx bx-left-arrow-alt'></i>返回首页
            </a>
        </div>
    </div>

    <footer class="footer">
        <div class="container">
            <p>© 2025 咖啡会 - 智能咖啡馆推荐服务 | 数据来源：高德地图</p>
        </div>
    </footer>

    <script type="text/javascript">
        // 定义全局变量存储标记点数据
        var markersData = {markers_json};

        // 配置高德地图安全密钥
        window._AMapSecurityConfig = {{
            securityJsCode: "",
        }};

        // 等待页面加载完成再加载地图
        window.onload = function() {{
            // 动态加载高德地图API
            var script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://webapi.amap.com/loader.js';
            script.onload = function() {{
                AMapLoader.load({{
                    key: "5cdbaed6e00545f6607d0f1263b67bd6", // 使用您提供的Key
                    version: "2.0",
                    plugins: ["AMap.Scale", "AMap.ToolBar"],
                    AMapUI: {{
                        version: "1.1",
                        plugins: ["overlay/SimpleMarker"],
                    }}
                }})
                .then(function(AMap) {{
                    initMap(AMap);
                }})
                .catch(function(e) {{
                    console.error('地图加载失败:', e);
                }});
            }};
            document.body.appendChild(script);

            // 添加咖啡馆卡片动画效果
            animateCafeCards();
        }};

        // 初始化地图的回调函数
        function initMap(AMap) {{
            // 创建地图实例
            var map = new AMap.Map('map', {{
                zoom: 12,
                center: [{center_point[0]}, {center_point[1]}],
                resizeEnable: true,
                viewMode: '3D'
            }});

            // 添加地图控件
            map.addControl(new AMap.ToolBar());
            map.addControl(new AMap.Scale());

            // 存储所有标记点
            var markers = [];

            // 为不同类型的标记创建不同的样式
            markersData.forEach(function(item) {{
                var markerContent;
                var position = new AMap.LngLat(item.position[0], item.position[1]);

                if (item.icon === 'center') {{
                    // 最佳会面点 - 绿色
                    markerContent = `
                        <div style="background-color: #2ecc71; width: 24px; height: 24px; border-radius: 12px;
                                    border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.3);">
                        </div>`;
                }} else if (item.icon === 'location') {{
                    // 用户地点 - 蓝色
                    markerContent = `
                        <div style="background-color: #3498db; width: 24px; height: 24px; border-radius: 12px;
                                    border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.3);">
                        </div>`;
                }} else {{
                    // 咖啡馆 - 红色
                    markerContent = `
                        <div style="background-color: #e74c3c; width: 24px; height: 24px; border-radius: 12px;
                                    border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.3);">
                        </div>`;
                }}

                // 创建自定义标记
                var marker = new AMap.Marker({{
                    position: position,
                    content: markerContent,
                    title: item.name,
                    anchor: 'center',
                    offset: new AMap.Pixel(0, 0)
                }});

                // 创建信息窗体
                var infoWindow = new AMap.InfoWindow({{
                    content: '<div style="padding:10px;font-size:14px;">' + item.name + '</div>',
                    offset: new AMap.Pixel(0, -12)
                }});

                // 绑定点击事件
                marker.on('click', function() {{
                    infoWindow.open(map, marker.getPosition());
                }});

                markers.push(marker);
                marker.setMap(map);
            }});

            // 添加路线规划功能
            if (markersData.length > 1) {{
                var pathCoordinates = [];
                markersData.filter(item => item.icon !== 'cafe').forEach(function(item) {{
                    pathCoordinates.push(new AMap.LngLat(item.position[0], item.position[1]));
                }});

                // 绘制连接线
                var polyline = new AMap.Polyline({{
                    path: pathCoordinates,
                    strokeColor: '#3498db',  // 线颜色
                    strokeWeight: 4,         // 线宽
                    strokeStyle: 'dashed',   // 线样式
                    strokeDasharray: [5, 5], // 虚线样式
                    lineJoin: 'round'        // 折线拐点连接处样式
                }});

                polyline.setMap(map);
            }}

            // 自动调整地图视野以包含所有标记
            map.setFitView(markers);
        }}

        // 咖啡馆卡片动画
        function animateCafeCards() {{
            const cards = document.querySelectorAll('.cafe-card');

            // 检查IntersectionObserver是否可用
            if ('IntersectionObserver' in window) {{
                const observer = new IntersectionObserver((entries) => {{
                    entries.forEach(entry => {{
                        if (entry.isIntersecting) {{
                            entry.target.style.opacity = 1;
                            entry.target.style.transform = 'translateY(0)';
                            observer.unobserve(entry.target);
                        }}
                    }});
                }}, {{ threshold: 0.1 }});

                cards.forEach((card, index) => {{
                    card.style.opacity = 0;
                    card.style.transform = 'translateY(30px)';
                    card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                    card.style.transitionDelay = (index * 0.1) + 's';
                    observer.observe(card);
                }});
            }} else {{
                // 回退方案 - 简单的延迟动画
                cards.forEach((card, index) => {{
                    card.style.opacity = 0;
                    card.style.transform = 'translateY(30px)';
                    card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';

                    setTimeout(() => {{
                        card.style.opacity = 1;
                        card.style.transform = 'translateY(0)';
                    }}, 300 + (index * 100));
                }});
            }}
        }}
    </script>
</body>
</html>"""

        # 完整HTML输出
        return html

    def _format_result_text(
        self,
        locations: List[Dict],
        cafes: List[Dict],
        html_path: str
    ) -> str:
        """格式化返回结果文本"""
        num_cafes = len(cafes)

        result = [
            f"## 已为您找到{num_cafes}家适合会面的咖啡馆",
            "",
            "### 推荐咖啡馆:",
        ]

        for i, cafe in enumerate(cafes):
            rating = cafe.get("biz_ext", {}).get("rating", "暂无评分")
            address = cafe.get("address", "地址未知")
            result.append(f"{i+1}. **{cafe['name']}** (评分: {rating})")
            result.append(f"   地址: {address}")
            result.append("")

        # 只返回文件名，不包含完整路径
        result.append(f"HTML页面: {os.path.basename(html_path)}")
        result.append("可在浏览器中打开查看详细地图和咖啡馆信息。")

        return "\n".join(result)

    def _generate_search_process(
        self,
        locations: List[Dict],
        center_point: Tuple[float, float],
        user_requirements: str
    ) -> str:
        """生成搜索过程的HTML内容，模拟AI代理思考过程"""

        # 初始化搜索过程步骤
        search_steps = []

        # 步骤1: 分析用户地点
        location_analysis = "<ul>"
        for idx, loc in enumerate(locations):
            location_analysis += f"<li>分析位置 {idx+1}: <strong>{loc['name']}</strong></li>"
        location_analysis += "</ul>"

        search_steps.append({
            "icon": "bx-map-pin",
            "title": "分析用户位置信息",
            "content": f"<p>我检测到{len(locations)}个不同的位置。正在分析它们的地理分布...</p>{location_analysis}"
        })

        # 步骤2: 显示正在操作高德地图寻找最佳咖啡馆的位置
        search_steps.append({
            "icon": "bx-map",
            "title": "正在操作高德地图",
            "content": """
            <p>正在操作高德地图寻找最佳咖啡馆的位置...</p>
            <div class="map-operation-animation">
                <div class="map-bg"></div>
                <div class="map-cursor"></div>
                <div class="map-search-indicator"></div>
            </div>
            """
        })

        # 步骤3: 分析额外需求
        requirement_analysis = ""
        if user_requirements:
            requirement_keywords = {
                "停车": ["停车", "车位", "停车场"],
                "安静": ["安静", "环境好", "氛围"],
                "商务": ["商务", "会议", "办公"],
                "交通": ["交通", "地铁", "公交"]
            }

            detected_requirements = []
            for key, keywords in requirement_keywords.items():
                if any(kw in user_requirements for kw in keywords):
                    detected_requirements.append(key)

            if detected_requirements:
                requirement_analysis = f"<p>我从您的需求中检测到以下关键偏好:</p><ul>"
                for req in detected_requirements:
                    requirement_analysis += f"<li><strong>{req}</strong>: 将优先考虑{req}便利的咖啡馆</li>"
                requirement_analysis += "</ul>"
            else:
                requirement_analysis = "<p>您没有提供特定的需求偏好，将基于综合评分和距离推荐最佳咖啡馆。</p>"
        else:
            requirement_analysis = "<p>未提供特殊需求，将根据评分和位置便利性进行推荐。</p>"

        search_steps.append({
            "icon": "bx-list-check",
            "title": "分析用户特殊需求",
            "content": requirement_analysis
        })

        # 步骤4: 搜索周边咖啡馆动画
        search_cafes_explanation = """
        <p>我正在以最佳会面点为中心，搜索周边2公里范围内的咖啡馆...</p>
        <div class="search-animation">
            <div class="radar-circle"></div>
            <div class="radar-circle"></div>
            <div class="radar-circle"></div>
            <div class="center-point"></div>
        </div>
        """

        search_steps.append({
            "icon": "bx-search-alt",
            "title": "搜索周边咖啡馆",
            "content": search_cafes_explanation
        })

        # 步骤5: 排序和筛选
        ranking_explanation = """
        <p>我已找到多家咖啡馆，正在根据综合评分对它们进行排名...</p>
        <div class="ranking-result">
            <div class="result-bar" style="width: 95%;">咖啡评分</div>
            <div class="result-bar" style="width: 85%;">距离便利性</div>
            <div class="result-bar" style="width: 75%;">环境舒适度</div>
            <div class="result-bar" style="width: 65%;">交通便利性</div>
        </div>
        """

        search_steps.append({
            "icon": "bx-sort",
            "title": "对咖啡馆进行排名",
            "content": ranking_explanation
        })

        # 生成HTML
        search_process_html = ""
        for idx, step in enumerate(search_steps):
            search_process_html += f"""
            <div class="process-step" data-step="{idx+1}">
                <div class="step-icon">
                    <i class='bx {step["icon"]}'></i>
                    <div class="step-number">{idx+1}</div>
                </div>
                <div class="step-content">
                    <h3 class="step-title">{step["title"]}</h3>
                    <div class="step-details">
                        {step["content"]}
                    </div>
                </div>
            </div>
            """

        # 加入自动展开步骤的JavaScrip函数
        search_process_javascript = """
        <script>
        // 在页面加载完成后，自动按顺序展示搜索步骤
        document.addEventListener('DOMContentLoaded', function() {
            const steps = document.querySelectorAll('.process-step');
            let currentStep = 0;

            function showNextStep() {
                if (currentStep < steps.length) {
                    steps[currentStep].classList.add('active');
                    currentStep++;
                    setTimeout(showNextStep, 1500);
                }
            }

            setTimeout(showNextStep, 500);
        });
        </script>
        """

        return f"""
        <div class="card search-process-card">
            <h2 class="section-title"><i class='bx bx-bot'></i>AI 搜索过程</h2>
            <div class="search-process">
                {search_process_html}
            </div>
            {search_process_javascript}
        </div>
        """

