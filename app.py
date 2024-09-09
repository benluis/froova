from flask import Flask, render_template, request, redirect, url_for
import os
from utils import save_pdf, extract_text_from_pdf, extract_ingredients_from_text
from pathlib import Path

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        method = request.form.get('method')
        if method == 'link':
            return redirect(url_for('input_link'))
        elif method == 'manual':
            return redirect(url_for('input_manual'))
    return render_template('home.html')

@app.route('/input_link', methods=['GET', 'POST'])
def input_link():
    if request.method == 'POST':
        url = request.form['url']
        dietary_restrictions = request.form['dietary_restrictions']
        pdf_path = save_pdf(url)
        recipe_text = extract_text_from_pdf(pdf_path)
        standardized_ingredients = extract_ingredients_from_text(recipe_text, dietary_restrictions)
        return render_template('results.html', ingredients=standardized_ingredients)
    return render_template('input_link.html')

@app.route('/input_manual', methods=['GET', 'POST'])
def input_manual():
    if request.method == 'POST':
        ingredients_list = request.form['ingredients']
        dietary_restrictions = request.form['dietary_restrictions']
        standardized_ingredients = extract_ingredients_from_text(ingredients_list, dietary_restrictions)
        return render_template('results.html', ingredients=standardized_ingredients)
    return render_template('input_manual.html')


@app.route('/submit_recipe', methods=['POST'])
def submit_recipe():
    allergies = request.form.get('allergies')
    dietary_preferences = request.form.get('dietary_preferences')
    recipe_link = request.form.get('recipe_link')
    manual_ingredients = request.form.get('ingredients')

    dietary_restrictions = f"Allergies: {allergies}, Preferences: {dietary_preferences}"

    if recipe_link:
        # Assuming a function to process the recipe link exists
        processed_data = process_recipe_link(recipe_link, dietary_restrictions)
    elif manual_ingredients:
        # Assuming a function to process manually entered ingredients exists
        processed_data = process_manual_ingredients(manual_ingredients, dietary_restrictions)

    # Redirect to a results page with processed data or back to home with an error/message
    return render_template('results.html', data=processed_data)


if __name__ == '__main__':
    app.run(debug=True)
