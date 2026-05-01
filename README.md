# BiznesAI — Bank KMB Analytical Platform 🚀

**BiznesAI** is an advanced, AI-powered business assessment and analytics platform designed specifically for the Uzbekistan Industrial and Construction Bank (SQB - O'zbekiston Sanoat-Qurilish Banki). It acts as an intelligent co-pilot for bank credit analysts, automating the evaluation of business proposals, minimizing risks, and providing deep insights into market viability, demand forecasting, and financial stability.

---

## 🌟 Key Advantages

- **Data-Driven Credit Decisions**: Replaces subjective human analysis with mathematically backed forecasts and unbiased AI evaluations.
- **Reduced Risk Exposure**: Identifies hidden market saturation, high churn rates, and local competitor threats before granting a loan.
- **Faster Processing Times**: Reduces manual analysis time from days to mere minutes, instantly generating a comprehensive 5-block assessment report.
- **Zero-Downtime Reliability**: Engineered with an **Intelligent AI Failover Mechanism**. If one AI provider (e.g., Gemini) hits a rate limit, the system instantly switches to another (OpenAI, AICC, Anthropic, or HuggingFace) with zero disruption to the user.
- **Uzbek Localization**: The entire platform, from the frontend UI to the AI's analytical output, is deeply localized for the Uzbekistan market, taking into account local holidays (Navroz, Ramadan), purchasing power, and regional dynamics.

---

## 🔥 Strong Abilities & Core Features

### 1. 🤖 Multi-Model AI Engine with Auto-Failover
BiznesAI integrates multiple Large Language Models (LLMs) to ensure constant uptime:
- Supported Engines: **Google Gemini**, **OpenAI GPT-4**, **AI.CC (Proxy)**, **Anthropic Claude**, and **HuggingFace**.
- **Smart Dispatcher**: Automatically detects API limits (429 errors), caches the broken provider to disable it on the frontend UI, and instantly falls back to the next available model.
- **Synthetic Mock Mode**: If all API keys are exhausted, the app seamlessly switches to a highly realistic, rule-based Mock Mode without breaking the user experience.

### 2. 📊 Advanced Financial Simulations (Monte Carlo)
- Runs **10,000-iteration Monte Carlo simulations** on the backend to predict:
  - Likelihood of business survival (%)
  - Break-Even Point (BEP) in months
  - Expected 12-month and 36-month Return on Investment (ROI)
  - Unit Economics (LTV vs CAC ratios, Gross Margins)
- Matches outputs directly against **SQB Bank's internal credit rules** (e.g., Debt Service Coverage Ratios).

### 3. 🗺️ Location & Geospatial Intelligence
- Integrated **Leaflet.js** mapping allows users to drop a pin on the exact planned location.
- **Competitor Mapping**: Calculates the exact number of competitors within 300-meter and 1-kilometer radiuses.
- Evaluates the "Anchor Effect" (proximity to malls, bazaars, schools, and transport hubs) to estimate foot traffic and 5/10-minute isochrone demand.

### 4. 🏢 Industry-Specific Deep Dives
Unlike generic tools, BiznesAI applies specialized logical frameworks based on the industry:
- **Hotels / Tourism**: Forecasts RevPAR (Revenue Per Available Room), seasonal occupancy patterns, and distance to airports/attractions.
- **Construction**: Models multi-phase 60-month cash flows, identifying high-risk "Phase 1" capital drain before the first income.
- **Textiles & Manufacturing**: Scores export readiness based on ISO/GOTS certifications, machinery age, and existing buyer pipelines.

### 5. 📈 Premium Dashboard & PDF Reporting
- **Interactive Visualizations**: Powered by **Chart.js**, the dashboard dynamically visualizes demand distribution, competitor threat levels, and financial projections.
- **Professional PDF Generation**: Generates bank-branded, downloadable PDF reports summarizing the final AI verdict, complete with "Credit Tier" (Good, Moderate, High Risk) and confidence scores.
- **Theme Support**: Includes a modern, glass-morphic UI with full Light/Dark mode support for optimal analyst comfort.

---

## 🛠️ Technology Stack

- **Backend**: Python, Django (with Celery & Redis for asynchronous AI processing)
- **Frontend**: HTML5, CSS3 (Bootstrap 5, Custom CSS variables for theming), Vanilla JavaScript
- **Visualization & Maps**: Chart.js, Leaflet.js
- **AI Integration**: Custom `ai_dispatcher` with official Python SDKs (google-generativeai, openai, anthropic, huggingface_hub)
- **Scientific/Math Libraries**: NumPy, Pandas, Scikit-learn (used for synthetic data modeling and statistical percentiles)

---

## 🚀 Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure Environment Variables**:
   Update your `.env` file with the required AI provider API keys.
3. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```
4. **Start the Development Server**:
   ```bash
   python manage.py runserver
   ```
   *Note: For background AI tasks, make sure to configure and run your Celery worker and Redis server.*

---

