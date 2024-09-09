import os
import openai
import pandas as pd
import pdfplumber
import glob
from time import sleep
from openai import completions
from playwright.sync_api import sync_playwright
from io import StringIO
from urllib.parse import unquote, urlparse, parse_qs
from pathlib import Path
from sprouts_scraper import *
from target_scraper import *
from traders_joe_scraper import *
from lidl_scraper import *

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

# Function that iterates over DataFrame and calls the scraper for each ingredient
def process_ingredients_list(dataframe):
    # List of scrapers for different stores
    scrapers = {
        #'Target': scrape_target_products,
        'Lidl': scrape_lidl_products,
        'TraderJoes': scrape_trader_joes_products,
        'Sprouts': scrape_sprouts_products
    }

    # Iterate through each row of the DataFrame and scrape using each store's scraper
    for index, row in dataframe.iterrows():
        ingredient = row['Name']  # Assuming 'Name' column contains the ingredient names
        print(f"Processing {ingredient}")

        # Loop through each scraper and call it directly
        for store, scraper_method in scrapers.items():
            print(f"Scraping {ingredient} from {store}")
            # Directly call the scraper method without using a wrapper
            scraper_method(ingredient)  # Pass the ingredient directly to the scraper function

    # After scraping, combine CSV files for each store
    print("Combining CSV files for each store...")
    combine_csv_files("target_*.csv", "combined_target.csv")
    combine_csv_files("lidl_*.csv", "combined_lidl.csv")
    combine_csv_files("trader_joes_*.csv", "combined_trader_joes.csv")
    combine_csv_files("sprouts_*.csv", "combined_sprouts.csv")

    # Combine all the "combined" CSVs into one final CSV
    print("Combining all store CSV files into one...")
    combine_csv_files("combined_*.csv", "final_combined_products.csv")

    print("All data has been scraped and combined successfully.")

def combine_csv_files(pattern, output_filename):
    # Use glob to match files using a wildcard pattern
    files = glob.glob(pattern)

    # List to store dataframes
    df_list = []

    # Loop through the matched files and read each CSV into a dataframe
    for file in files:
        df = pd.read_csv(file)
        df_list.append(df)

    # Concatenate all dataframes into one
    combined_df = pd.concat(df_list, ignore_index=True)

    # Remove rows with any missing (NaN) values
    #combined_df_cleaned = combined_df.dropna()

    # Save the cleaned combined dataframe to a new CSV file
    combined_df.to_csv(output_filename, index=False)

    print(f"Combined and cleaned CSV saved to {output_filename}")


def find_cheapest_from_csv(dataframe):
    # Convert the DataFrame to a CSV string (comma-separated values)
    csv_string_io = StringIO()
    dataframe.to_csv(csv_string_io, index=False)
    csv_string = csv_string_io.getvalue().strip()  # Get the CSV string

    # Define the messages for OpenAI API request
    messages = [
        {"role": "system", "content": """
        You are an expert on grocery prices. Output a CSV list of the cheapest ingredients across different stores.
        Each ingredient should be on a new line, using the following columns:
        - type (product type from the csv in the column: type)
        - name (enclosed in quotes if it contains commas)
        - volume (write 'NaN' if not applicable)
        - weight (write 'NaN' if not applicable)
        - price
        - store
        Provide only the CSV output without any additional commentary.
        """},
        {"role": "user", "content": f"{csv_string} I have uploaded a CSV dataset with grocery products from multiple stores. Please analyze this data and generate a CSV list that identifies the absolute cheapest product for each type across all the stores. The resulting CSV should include the following columns: type, name, volume (if applicable, otherwise 'NaN'), weight (if applicable, otherwise 'NaN'), price, store, and a boolean 'cheapest' set to 'True' for each item."}
    ]

    try:
        # Make a request to OpenAI API using chat.completions.create
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",  # Use the appropriate model
            messages=messages
        )

        # Fetch the GPT-generated message content correctly
        gpt_output = response.choices[0].message.content.strip()

        # Remove the first 6 characters and the last 3 characters
        processed_output = gpt_output[6:-3]

        # Display the GPT output for debugging
        print("Processed GPT Output (Substring):")
        print(processed_output)

        # Try to fix incomplete lines by removing the last incomplete line
        if not processed_output.endswith('\n'):
            processed_output = processed_output.rsplit('\n', 1)[0]

        # Convert the substring (processed_output) to a DataFrame
        try:
            csv_string_io = StringIO(processed_output)  # Use StringIO to simulate a file-like object
            ingredients_list = pd.read_csv(csv_string_io, quotechar='"')  # Handle quoted fields properly
        except pd.errors.ParserError as parse_error:
            # If there is a parsing error, display the error and the problematic line
            print(f"CSV Parsing Error: {parse_error}")
            return pd.DataFrame()  # Return an empty DataFrame on error

        print("\nIngredients List DataFrame:")
        print(ingredients_list)

        # Save DataFrame to CSV file
        ingredients_list.to_csv('processed_combined.csv', index=False)
        print("Ingredients list saved to 'processed_combined.csv'.")

        return ingredients_list

    except Exception as e:
        print(f"\nError processing the CSV data: {e}")
        return pd.DataFrame()  # Return an empty DataFrame on error



def strip_image_url_and_clean(dataframe):
    # Check if 'image_url' column exists and remove it
    if 'image_url' in dataframe.columns:
        dataframe = dataframe.drop(columns=['image_url'])

    # Remove rows with missing (NaN) values
    dataframe = dataframe.dropna()

    # Return the cleaned DataFrame
    return dataframe

def save_pdf(url):
    directory = os.path.join(os.path.dirname(__file__), 'recipes')
    if not os.path.exists(directory):
        os.makedirs(directory)
    filename = os.path.join(directory, 'output.pdf')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        pdf_options = {"format": 'A4', "print_background": True}
        page.pdf(path=filename, **pdf_options)
        browser.close()
        print(f"PDF saved as {filename}")

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
