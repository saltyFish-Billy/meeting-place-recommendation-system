# 🌟 咖啡会 - 智能会面地点推荐系统

<p align="center">
  <img src="https://img.shields.io/badge/版本-1.0.0-blue.svg" alt="版本">
  <img src="https://img.shields.io/badge/许可证-MIT-green.svg" alt="许可证">
  <img src="https://img.shields.io/badge/平台-Web-orange.svg" alt="平台">
  <img src="https://img.shields.io/badge/基于-OpenManus-purple.svg" alt="基于">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/OpenManus/branding/main/logo.png" alt="咖啡会" width="200">
</p>

> "让每次会面都成为完美时刻，让每杯咖啡都值得回味" —— 咖啡会

## 📖 项目介绍

**咖啡会**是一个基于OpenManus智能代理框架的创新应用，专为解决"多人会面地点选择"这一日常难题而设计。在城市生活节奏日益加快的今天，找到一个对所有人都公平、舒适且高质量的会面场所变得越来越重要。咖啡会通过人工智能和地图数据分析，为您智能推荐最佳会面咖啡馆，让社交活动规划变得轻松愉快。

### 💡 核心特性

- **多点平衡算法**：基于所有参与者位置，智能计算最公平、各方最舒服的会面点
- **全方位咖啡馆评估**：综合考量评分、距离、环境、服务、交通等多维因素
- **个性化需求满足**：支持停车便利、环境安静、商务会谈等特殊偏好
- **高颜值交互界面**：精心设计的Web界面，支持响应式布局
- **直观地图可视化**：整合高德地图API，直观展示地理位置和路线规划
- **智能交通建议**：提供到达方式和停车建议，解决出行顾虑

## 🔍 项目展示

<p align="center">
  <a href="docs/videos/coffee_meet_demo.mp4">
    <strong>📹 点击查看项目演示视频</strong>
  </a>
</p>

<p align="center">
  <em>项目演示 - 多地点咖啡馆智能推荐过程</em>
</p>

> 注意：GitHub不支持直接播放视频，请下载后在本地观看，或克隆仓库后查看。

## 🚀 快速开始

### 系统要求

- Python 3.8+
- 网络连接
- 现代浏览器（Chrome, Firefox, Safari等）

### 安装指南

1. 克隆本仓库到本地：

```bash
git clone https://github.com/yourusername/coffee-meet.git
cd coffee-meet
```

2. 创建并激活虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. 安装依赖项：

```bash
pip install -r requirements.txt
```
把各个必要的api_key和安全密钥都填入

4. 启动Web服务器：

```bash
python web_server.py
```

5. 打开浏览器访问：

```
http://localhost:8000
```

## 🎯 使用方法

1. **输入聚会人员所在位置**
   - 至少需要输入两个不同的地点
   - 支持详细地址或地标名称

2. **指定特殊需求（可选）**
   - 例如：安静环境、停车方便、适合商务会谈等

3. **点击"查找最佳会面咖啡馆"按钮**
   - 系统将计算最佳会面点并推荐附近咖啡馆

4. **查看结果页面**
   - 浏览推荐咖啡馆列表和详细信息
   - 查看交互式地图和位置标记
   - 获取交通和停车建议

## 🧠 技术原理

### 核心算法流程

1. **地理编码转换**：将用户输入的地点描述转换为精确经纬度坐标
2. **中心点计算**：基于所有参与者位置智能计算最佳会面地点
3. **POI搜索**：通过高德地图在中心点附近搜索咖啡馆
4. **多维度排序**：根据评分、距离、用户需求等因素对咖啡馆进行智能排序
5. **可视化呈现**：生成交互式HTML页面，展示详细结果和动态地图

### 技术栈

- **后端**：FastAPI, OpenManus, Python异步编程
- **前端**：HTML5, CSS3, JavaScript, 响应式设计
- **地图服务**：高德地图
- **数据处理**：Pydantic, aiohttp


## 💻 开发者指南

### 项目结构

```
OpenManus_web/
├── app/                 # 核心应用代码
│   ├── agent/           # 智能代理模块
│   ├── tool/            # 工具集合
│   │   ├── cafe_recommender.py  # 咖啡推荐工具
│   │   └── ...
│   └── ...
├── workspace/           # 静态资源和生成文件
│   ├── cafe_finder.html # 主搜索页面
│   └── js_src/          # 生成的结果页面
├── web_server.py        # Web服务器入口
├── requirements.txt     # 依赖项配置
└── README.md            # 项目文档
```

### 扩展开发

1. **添加新的评价维度**

```python
# 在_rank_cafes方法中添加新的评价标准
def _rank_cafes(self, cafes, center_point, user_requirements):
    # 添加新的评分维度，如环保认证
    if "环保" in user_requirements:
        # 为环保咖啡馆加分
        # ...
```

2. **自定义UI主题**

修改HTML模板中的CSS变量即可轻松更换主题色系：

```css
:root {
    --primary: #新颜色代码;
    --primary-light: #新颜色代码;
    --primary-dark: #新颜色代码;
    /* 其他颜色变量 */
}
```

## 📊 性能与限制

- 支持同时处理最多5个不同地点
- 地图API调用可能受到网络状况影响
- 咖啡馆数据依赖高德地图POI数据库更新

## 🌱 未来计划

- [ ] 整合更多地图服务提供商
- [ ] 添加用户偏好记忆功能
- [ ] 支持公共交通时间计算
- [ ] 增加室内导航功能
- [ ] 开发移动应用版本

## 🤝 贡献指南

欢迎贡献代码、提交问题或改进建议！请遵循以下步骤：

1. Fork 这个仓库
2. 创建您的特性分支：`git checkout -b feature/amazing-feature`
3. 提交您的更改：`git commit -m '添加一些惊人的特性'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 提交拉取请求

## 📜 版权和许可

本项目基于MIT许可证开源 - 详情请参阅 [LICENSE](LICENSE) 文件

## 👏 致谢

- [OpenManus] - 提供基础智能代理框架
- [高德地图](https://lbs.amap.com/) - 提供地图和POI数据服务
- 所有贡献者和使用者 - 感谢您的支持和反馈

## 📬 联系方式

- 项目维护者: [Alex-Fan]
- 项目仓库: [GitHub](https://github.com/franskey-0112/CafeMeet)

---

<p align="center">用智能，找到心仪的咖啡馆 ☕</p>
