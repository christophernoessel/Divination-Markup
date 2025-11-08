import tkinter as tk
from tkinter import filedialog, Text
import os
import json

def select_file():
    root = tk.Tk()
    root.withdraw()  # we don't want a full GUI, so keep the root window from appearing
    file_path = filedialog.askopenfilename()  # show an "Open" dialog box and return the path to the selected file
    root.destroy()
    return file_path

def read_file_contents(file_path):
    if not file_path:
        print("No file selected.")
        return

    with open(file_path, 'r') as file:
        full_text = file.read()
    return full_text

def write_file(file_name, contents):
    with open(file_name, 'w') as file:
        file.write(contents)
    
def main():
    file_path = select_file()
    
if __name__ == "__main__":
    main()

def write_dicts_to_file(dict_list, file_path="debug_output.txt"):
    """
    Write a list of dictionaries to a text file with pretty-printed JSON formatting.

    Parameters:
    - dict_list: A list of dictionaries to be written to the file.
    - file_path: The path to the text file where the data will be written.
    """
    # Open the file at file_path in write mode ('w')
    with open(file_path, 'w') as file:
        # Use json.dump() to write the dict_list to the file with indentation for readability
        json.dump(dict_list, file, indent=4, ensure_ascii=False)

def append_to_file(text, base_filename="output-"):
    # Generate the datetime stamp in the format YearMonthDay-HourMinuteSecond
    datetime_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Form the full filename with the datetime stamp appended to the base filename
    filename = f"{base_filename}{datetime_stamp}.txt"
    
    # Check if a file starting with the base filename already exists in the current directory
    # This will check for any file that starts with "output-" and has a ".txt" extension
    existing_files = [f for f in os.listdir('.') if os.path.isfile(f) and f.startswith(base_filename) and f.endswith(".txt")]
    if existing_files:
        # If there are existing files, use the most recently created one based on the naming convention
        filename = sorted(existing_files)[-1]
    
    # Open the file in append mode and write the text to it
    with open(filename, 'a') as file:
        file.write(text + '\n')  # Append a newline character for formatting

def compare_texts(text1, text2):
    stripped_text1 = strip_markup_tags(text1)
    stripped_text2 = strip_markup_tags(text2)
    return stripped_text1 == stripped_text2