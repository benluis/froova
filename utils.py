import os
import openai
import pandas as pd
import pdfplumber
from time import sleep
from openai import completions
from playwright.sync_api import sync_playwright
from io import StringIO
from urllib.parse import unquote, urlparse, parse_qs

def read_api_key():
    api_key_path = os.path.join(os.path.dirname(__file__), 'api_key.txt')
    with open(api_key_path, 'r') as file:
        return file.read().strip()

openai.api_key = read_api_key()

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text()
    return text

def extract_ingredients_from_text(text, dietary_restrictions):
    messages = [
        {"role": "system", "content": "You are a knowledgeable chef. Please provide a list of ingredients in CSV format. Each ingredient should be on a new line, with the columns: Name, Volume, Weight, Can_not_eat. 'Can_not_eat' should be 'True' if the ingredient matches any listed dietary restrictions or allergies, otherwise 'False'. If Volume or Weight is not applicable, write 'NaN'. Please only output the comma-separated values and don't say anything else."},
        {"role": "user", "content": f"The recipe content is: {text}\nDietary restrictions: {dietary_restrictions}"}
    ]

    # Using the OpenAI API to get the completion
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    # Fetch the GPT-generated message content
    gpt_output = response.choices[0].message.content.strip()
    print("GPT Output (CSV String):")
    print(gpt_output)  # Printing the GPT output

    try:
        # Convert the CSV string to a DataFrame
        csv_string_io = StringIO(gpt_output)  # Use StringIO to simulate a file-like object
        ingredients_list = pd.read_csv(csv_string_io)
        print("\nIngredients List DataFrame:")
        print(ingredients_list)

        # Save DataFrame to CSV file
        ingredients_list.to_csv('ingredients_list.csv', index=False)
        print("Ingredients list saved to 'ingredients_list.csv'.")

        return ingredients_list
    except Exception as e:
        print(f"\nError processing the CSV data: {e}")
        return pd.DataFrame()  # Return an empty DataFrame on error

def prompt_for_replacements(ingredients_df):
    if "Can_not_eat" in ingredients_df.columns and ingredients_df['Can_not_eat'].any():
        # Filter to only those ingredients that cannot be eaten
        restricted_ingredients = ingredients_df[ingredients_df['Can_not_eat'] == True]

        for index, row in restricted_ingredients.iterrows():
            original_ingredient = row['Name']
            # Prompt GPT for a single replacement suggestion
            prompt_text = f"Provide a single ingredient replacement for {original_ingredient}. Make sure you only respond with the name of the substitution only, do not say anything else or else. Also make sure the state of matter of the ingredient is not changed. For example dont, replace eggs with a solid, replace it with something else that is liquid"
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a knowledgeable chef tasked with suggesting a single ingredient replacement."},
                          {"role": "user", "content": prompt_text}]
            )
            suggested_replacement = response.choices[0].message.content.strip()

            # Ask user for approval to replace
            user_approval = input(f"Do you want to replace {original_ingredient} with {suggested_replacement}? (Yes/No): ")
            if user_approval.lower() == 'yes':
                # Prompt GPT for volume and weight if the replacement is approved
                volume_weight_prompt = f"Provide the volume and weight for {suggested_replacement}, formatted as 'volume, weight'."
                volume_weight_response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": "You are a knowledgeable chef tasked with providing the volume and weight of an ingredient formatted as 'volume, weight'. Do not include any extra information."},
                              {"role": "user", "content": volume_weight_prompt}]
                )
                volume_and_weight = volume_weight_response.choices[0].message.content.strip()

                # Split the response into volume and weight
                if ", " in volume_and_weight:
                    volume, weight = volume_and_weight.split(", ")
                    ingredients_df.at[index, 'Name'] = suggested_replacement
                    ingredients_df.at[index, 'Volume'] = volume
                    ingredients_df.at[index, 'Weight'] = weight
                    ingredients_df.at[index, 'Can_not_eat'] = False
                else:
                    # If the format is not as expected, retain the existing volume and weight
                    ingredients_df.at[index, 'Name'] = suggested_replacement
                    ingredients_df.at[index, 'Can_not_eat'] = False

        # Save updated DataFrame to CSV file
        ingredients_df.to_csv('updated_ingredients_list.csv', index=False)
        print("Updated ingredients list saved to 'updated_ingredients_list.csv'.")
    else:
        print("No ingredients need to be replaced due to dietary restrictions.")

    return ingredients_df


def save_pdf(url, filename="output.pdf", retries=3, timeout=60000):
    """Save the webpage as a PDF after ensuring it is fully loaded. Retries if there is an error."""
    directory = os.path.join(os.path.dirname(__file__), 'recipes')
    if not os.path.exists(directory):
        os.makedirs(directory)

    filepath = os.path.join(directory, filename)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Turn off headless mode if needed
        page = browser.new_page()

        attempt = 0
        while attempt < retries:
            try:
                print(f"Attempting to load {url} (Attempt {attempt + 1})")

                # Attempt to load the page with a longer timeout and wait for full network idle
                page.goto(url, wait_until="networkidle", timeout=timeout)

                # Save the page as PDF
                pdf_options = {"format": 'A4', "print_background": True}
                page.pdf(path=filepath, **pdf_options)

                print(f"PDF saved as {filepath}")
                break  # Exit loop if successful

            except Exception as e:
                attempt += 1
                print(f"Error loading {url}: {e}")
                if attempt < retries:
                    print(f"Retrying in 5 seconds...")
                    sleep(5)  # Wait before retrying
                else:
                    print(f"Failed to save {url} after {retries} attempts.")

        browser.close()


def get_url_input():
    url = input("Please enter the URL of the webpage you want to convert to PDF: ")
    save_pdf(url)

def gather_user_info():
    name = input("What is your name? ")
    allergies = input("Do you have any allergies? If yes, please list them. If no, type 'None': ")
    dietary_preferences = input("Do you have any dietary preferences? ")

    print("\nPlease confirm the following information:")
    print(f"Name: {name}")
    print(f"Allergies: {allergies}")
    print(f"Dietary Preferences: {dietary_preferences}")

    confirmation = input("Is the above information correct? (Yes/No) ")
    if confirmation.lower() == 'yes':
        print("Thank you for confirming your details.")
        return allergies, dietary_preferences
    else:
        print("Let's try entering the information again.")
        return gather_user_info()

def store_selection():
    print("Please select your shopping preference:")
    print("1. Compare prices across multiple stores")
    print("2. Prefer a single store")
    choice = input("Enter your choice (1 or 2): ")
    while choice not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2.")
        choice = input("Enter your choice (1 or 2): ")
    if choice == '1':
        print("You have selected to compare prices across multiple stores.")
    elif choice == '2':
        store_name = input("Please enter the name of the store you prefer: ")
        print(f"You have selected to shop at {store_name}.")

def recipe_input_options(dietary_restrictions):
    print("How would you like to input your recipe?")
    print("1. Input a recipe link")
    print("2. Manually enter a list of ingredients")
    choice = input("Enter your choice (1 or 2): ")
    while choice not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2.")
        choice = input("Enter your choice (1 or 2): ")

    if choice == '1':
        url = input("Please enter the recipe link: ")
        save_pdf(url)
        pdf_path = os.path.join(os.path.dirname(__file__), 'recipes', 'output.pdf')
        recipe_text = extract_text_from_pdf(pdf_path)
        # The following line has been commented out to stop printing the extracted text
        # print("\nExtracted text from PDF:")
        # print(recipe_text)
        standardized_ingredients = extract_ingredients_from_text(recipe_text, dietary_restrictions)
        print("\nHere is the standardized ingredient list:")
        print(standardized_ingredients)

    elif choice == '2':
        ingredients = []
        print("Please enter your ingredients. Type 'done' when you finish.")
        while True:
            ingredient = input("Enter an ingredient (or type 'done' if you're finished): ")
            if ingredient.lower() == 'done':
                break
            ingredients.append(ingredient)

        if ingredients:
            standardized_ingredients = extract_ingredients_from_text(", ".join(ingredients), dietary_restrictions)
            print("\nHere is the standardized ingredient list:")
            print(standardized_ingredients)
