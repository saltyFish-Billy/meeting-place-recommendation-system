# 🌟 CoffeeMeet - Smart Meeting Location Recommendation System

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-Web-orange.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Based%20on-OpenManus-purple.svg" alt="Based on">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/OpenManus/branding/main/logo.png" alt="CoffeeMeet" width="200">
</p>

> "Make every meeting a perfect moment, make every cup of coffee worth savoring" — CoffeeMeet

## 📖 Project Introduction

**CoffeeMeet** is an innovative application based on the OpenManus intelligent agent framework, specifically designed to solve the daily challenge of "multi-person meeting location selection." In today's fast-paced urban lifestyle, finding a meeting place that is fair, comfortable, and high-quality for everyone involved has become increasingly important. CoffeeMeet uses artificial intelligence and map data analysis to intelligently recommend the best meeting cafes, making social activity planning easy and enjoyable.

### 💡 Core Features

- **Multi-point Balancing Algorithm**: Intelligently calculates the fairest meeting point based on all participants' locations
- **Comprehensive Cafe Evaluation**: Considers multiple factors including ratings, distance, environment, and service
- **Personalized Requirements**: Supports special preferences such as parking convenience, quiet environment, and business meetings
- **High-quality Interactive Interface**: Carefully designed web interface with responsive layout
- **Intuitive Map Visualization**: Integrates Amap API to visually display geographical locations and route planning
- **Smart Transportation Suggestions**: Provides arrival methods and parking suggestions to address travel concerns

## 🔍 Project Showcase

<p align="center">
  <video width="80%" controls>
    <source src="docs/videos/coffee_meet_demo.mp4" type="video/mp4">
    Your browser does not support the video tag, please upgrade your browser or use another one
  </video>
</p>

<p align="center">
  <em>Project demonstration video - Smart cafe recommendation process for multiple locations</em>
</p>

## 🚀 Quick Start

### System Requirements

- Python 3.8+
- Internet connection (for map API calls)
- Modern browser (Chrome, Firefox, Safari, etc.)

### Installation Guide

1. Clone this repository:

```bash
git clone https://github.com/franskey-0112/CafeMeet.git
cd CafeMeet
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the web server:

```bash
python web_server.py
```

5. Open your browser and visit:

```
http://localhost:8000
```

## 🎯 How to Use

1. **Enter Locations of All Participants**
   - At least two different locations are required
   - Supports detailed addresses or landmark names

2. **Specify Special Requirements (Optional)**
   - Examples: quiet environment, convenient parking, suitable for business meetings, etc.

3. **Click the "Find Best Meeting Cafe" Button**
   - The system will calculate the best meeting point and recommend nearby cafes

4. **View Results Page**
   - Browse the recommended cafe list and detailed information
   - View the interactive map and location markers
   - Get transportation and parking suggestions

## 🧠 Technical Principles

### Core Algorithm Flow

1. **Geocoding Conversion**: Convert user input location descriptions to precise latitude and longitude coordinates
2. **Center Point Calculation**: Calculate the optimal meeting center point based on all participants' locations
3. **POI Search**: Use Amap API to search for cafes near the center point
4. **Multi-dimensional Ranking**: Intelligently rank cafes based on rating, distance, user requirements, and other factors
5. **Visual Presentation**: Generate an interactive HTML page showing detailed results and a dynamic map

### Technology Stack

- **Backend**: FastAPI, OpenManus, Python Async Programming
- **Frontend**: HTML5, CSS3, JavaScript, Responsive Design
- **Map Service**: Amap API
- **Data Processing**: Pydantic, aiohttp

## 🔄 Workflow

<p align="center">
  <img src="docs/images/workflow.png" alt="Workflow" width="80%">
</p>

## 💻 Developer Guide

### Project Structure

```
OpenManus_web/
├── app/                 # Core application code
│   ├── agent/           # Intelligent agent modules
│   ├── tool/            # Tool collection
│   │   ├── cafe_recommender.py  # Cafe recommendation tool
│   │   └── ...
│   └── ...
├── workspace/           # Static resources and generated files
│   ├── cafe_finder.html # Main search page
│   └── js_src/          # Generated result pages
├── web_server.py        # Web server entry
├── requirements.txt     # Dependency configuration
└── README.md            # Project documentation
```

### Extension Development

1. **Adding New Evaluation Dimensions**

```python
# Add new evaluation criteria in the _rank_cafes method
def _rank_cafes(self, cafes, center_point, user_requirements):
    # Add new scoring dimension, such as eco-certification
    if "eco" in user_requirements:
        # Add points for eco-friendly cafes
        # ...
```

2. **Customizing UI Theme**

Modify the CSS variables in the HTML template to easily change the theme colors:

```css
:root {
    --primary: #new-color-code;
    --primary-light: #new-color-code;
    --primary-dark: #new-color-code;
    /* Other color variables */
}
```

## 📊 Performance and Limitations

- Supports processing up to 5 different locations simultaneously
- Map API calls may be affected by network conditions
- Cafe data depends on Amap POI database updates

## 🌱 Future Plans

- [ ] Integrate more map service providers
- [ ] Add user preference memory function
- [ ] Support public transportation time calculation
- [ ] Add indoor navigation functionality
- [ ] Develop mobile application version

## 🤝 Contribution Guidelines

Contributions of code, issue submissions, or improvement suggestions are welcome! Please follow these steps:

1. Fork this repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Submit a pull request

## 📜 Copyright and License

This project is open-sourced under the MIT License - see the [LICENSE](LICENSE) file for details

## 👏 Acknowledgements

- [OpenManus](https://github.com/OpenManus/OpenManus) - Providing the basic intelligent agent framework
- [Amap](https://lbs.amap.com/) - Providing map and POI data services
- All contributors and users - Thank you for your support and feedback

## 📬 Contact Information

- Project Maintainer: [Alex-Fan]
- Project Repository: [GitHub](https://github.com/franskey-0112/CafeMeet)

---

<p align="center">Use intelligence to find your favorite cafe ☕</p>
