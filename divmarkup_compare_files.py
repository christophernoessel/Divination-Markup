from file_functions             import *
from divmarkup_text_functions   import *
import difflib

def compare_files():
    ##print("First choose a source file with no markup")
    ##file1_path = select_file()
    ##print(file1_path)
    print("Loading marked_up_i_ching.txt…")
    file1_path = "/Users/christophernoessel/Documents/divination xml/universal_divtext_markup.py/marked_up_i_ching.txt"
    source_text = read_file_contents(file1_path)
    source_text = '\n'.join(line for line in source_text.splitlines() if line.strip())
    print()
    
    print("Now choose a marked-up file")
    file2_path = select_file()
    marked_up_text = read_file_contents(file2_path)
    marked_up_text = remove_markup_tags(marked_up_text)
    marked_up_text = '\n'.join(line for line in marked_up_text.splitlines() if line.strip())

    result = compare_strings_line_by_line(source_text, marked_up_text)
    for line in result:
        print(line)
        result = input("continue? y/n")
        if result == 'n':
            break

if __name__ == "__main__":
    compare_files()
