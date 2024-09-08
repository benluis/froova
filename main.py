from utils import *

def main():
    allergies, dietary_preferences = gather_user_info()
    dietary_restrictions = f"Allergies: {allergies}, Preferences: {dietary_preferences}"

    store_selection()
    recipe_input_options(dietary_restrictions)

if __name__ == "__main__":
    i = "https://www.google.com/search?q=inurl%3Ahttps%3A%2F%2Fwww.target.com%2Fp%2F+intitle%3Aflour"
    save_pdf(i)