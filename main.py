from utils import *

def main():
    allergies, dietary_preferences = gather_user_info()
    dietary_restrictions = f"Allergies: {allergies}, Preferences: {dietary_preferences}"

    store_selection()
    recipe_input_options(dietary_restrictions)

if __name__ == "__main__":
    main()