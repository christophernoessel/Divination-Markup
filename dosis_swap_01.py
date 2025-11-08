import re
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import os

def process_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()
    except IOError as e:
        print(f"Error reading file: {e}")
        return

    lines = content.split('\n')
    total_lines = len(lines)
    modified = False

    for i, line in enumerate(lines):
        line_modified = False
        tags = re.finditer(r'<(protasis|apodosis)([^>]*)>(.*?)</\1>', line)
        
        for match in tags:
            tag_type, attributes, text = match.groups()
            print(f"\nLine {i+1}: <{tag_type}{attributes}>{text}</{tag_type}>")
            user_input = input("Enter 'p' for protasis, 'a' for apodosis, 'strip' to strip tags, or press Enter to continue: ").strip().lower()
            
            if user_input == 'p' and tag_type == 'apodosis':
                line = line.replace(f'<apodosis{attributes}>{text}</apodosis>', f'<protasis{attributes}>{text}</protasis>', 1)
                line_modified = True
                print("Changed to protasis")
            elif user_input == 'a' and tag_type == 'protasis':
                line = line.replace(f'<protasis{attributes}>{text}</protasis>', f'<apodosis{attributes}>{text}</apodosis>', 1)
                line_modified = True
                print("Changed to apodosis")
            elif user_input == 'strip':
                line = line.replace(f'<{tag_type}{attributes}>{text}</{tag_type}>', text, 1)
                line_modified = True
                print("Tags stripped")
        
        if line_modified:
            lines[i] = line
            modified = True


    if modified:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{os.path.splitext(filename)[0]}_{timestamp}{os.path.splitext(filename)[1]}"
        try:
            with open(new_filename, 'w', encoding='utf-8') as file:
                file.write('\n'.join(lines))
            print(f"\nModified file saved as: {new_filename}")
        except IOError as e:
            print(f"\nError writing to file: {e}")
            
        # Calculate and display progress
        progress = (i + 1) / total_lines * 100
        print(f"===========> Progress: {progress:.2f}% complete")

# Create a root window and hide it
root = tk.Tk()
root.withdraw()

# Open file dialog to select a file from the desktop
desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
filename = filedialog.askopenfilename(
    initialdir=desktop_path,
    title="Select file",
    filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
)

if filename:
    print(f"Selected file: {filename}")
    process_file(filename)
else:
    print("No file selected. Exiting.")
