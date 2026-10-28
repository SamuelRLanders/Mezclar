from backend.app.naming.wordlist import ADJECTIVE_LIST, BLOCK_LIST, NOUN_LIST
import random

def generate_name() -> str:
    first_word = random.choice(ADJECTIVE_LIST)
    second_word = random.choice(NOUN_LIST)
    return f"{first_word} {second_word}"

def is_unique_name(name: str, used_names: set[str]) -> bool:
    return name not in used_names

def generate_unique_name(used_names: set[str], max_attempts: int = 10) -> str:
    for _ in range(max_attempts):
        name = generate_name()
        if is_unique_name(name, used_names):
            return name
    raise ValueError("Failed to generate a unique name after maximum attempts.")

def validate_name(name: str) -> bool:
    if name != None:
        words_in_name = name.split()
        for word in words_in_name:
            standardized_word = word.strip().lower()
            if standardized_word in BLOCK_LIST:
                return False
    return True
