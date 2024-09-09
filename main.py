from utils import *


def main():
    # Open AI API Key
    openai.api_key = read_api_key()

    # Ask for allergies and dietary preferences
    allergies, dietary_preferences = gather_user_info()

    # Make a list of it
    dietary_restrictions = f"Allergies: {allergies}, Preferences: {dietary_preferences}"

    # Get recipe from user
    recipe_input_options(dietary_restrictions)

    # Ingredients list from user
    ingredients_df = pd.read_csv(Path(__file__).parent / 'ingredients_list.csv')

    # Replace problematic items with Open AI
    x = prompt_for_replacements(ingredients_df)
    x.to_csv('updated_ingredients_list.csv')

    #updated_ingredients_df = pd.read_csv(Path(__file__).parent / 'updated_ingredients_list.csv')
    #process_ingredients_list(updated_ingredients_df)

    find_cheapest_from_csv(pd.read_csv(Path(__file__).parent / 'updated_ingredients_list.csv'))

    pd.read_csv(Path(__file__).parent / 'processed_combined.csv')
if __name__ == "__main__":
    main()