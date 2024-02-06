import re

def find_all_match_indices(main_string, substring):
    pattern = re.compile(substring, re.IGNORECASE)
    return [match.start() for match in re.finditer(pattern, main_string)]

# Example usage
main_string = "Python is fun. python is powerful. I love PYTHON!"
substring = "python"

indices = find_all_match_indices(main_string, substring)
print(indices)  # This should print [0, 16, 43]
