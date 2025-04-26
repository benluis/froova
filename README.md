# Recipe Assistant

A FastAPI application that helps you process recipes, manage ingredients with dietary restrictions, find ingredient substitutions, and create optimized shopping lists from multiple grocery stores.

## Features

- **Recipe Input**: Import recipes from URLs or paste directly
- **Ingredient Extraction**: Automatically extract ingredients from recipe text using AI
- **Dietary Restrictions**: Filter recipes based on allergies and dietary preferences
- **Ingredient Substitutions**: Get AI-powered alternative ingredients
- **Shopping List Generation**: Create shopping lists organized by store
- **Price Comparison**: Compare prices across different grocery stores (Walmart, Target, Sprouts, Lidl)

## Tech Stack

- **Backend**: Python, FastAPI
- **Data Processing**: Pandas
- **Web Scraping**: Selenium, BeautifulSoup
- **AI Integration**: OpenAI API
- **Frontend**: Jinja2 Templates

## Setup

### Prerequisites

- Python 3.8+
- Chrome browser (for web scraping)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/recipe-assistant.git
   cd recipe-assistant
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```

### Running the Application

Start the FastAPI server:
```bash
python main.py
```

The application will be available at http://localhost:8000

## Usage

1. **Submit a Recipe**
   - Navigate to http://localhost:8000/input-recipe
   - Enter a recipe URL or paste ingredient text
   - Specify any allergies or dietary preferences

2. **Review Ingredients**
   - The application extracts ingredients with AI
   - Review the extracted ingredients

3. **Choose Replacements**
   - Select alternatives for ingredients you want to replace

4. **Generate Shopping List**
   - Get a shopping list organized by store
   - Compare prices across different retailers
