import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox

def search_and_highlight(search_text):
    """
    Search the given text in the scrolled text widget, highlight it, and scroll to it if found.
    """
    # Remove previous highlights
    text_widget.tag_remove('found', '1.0', tk.END)
    
    # If search_text is not empty
    if search_text:
        # Start from the beginning (and use a case-insensitive search)
        index = '1.0'
        while True:
            index = text_widget.search(search_text, index, nocase=1, stopindex=tk.END)
            if not index: break
            # Calculate the end index
            last_index = f"{index}+{len(search_text)}c"
            text_widget.tag_add('found', index, last_index)
            index = last_index
        text_widget.tag_config('found', background='yellow')
        
        # Scroll to the first occurrence of the found text
        if text_widget.tag_ranges('found'):
            first_occurrence = text_widget.tag_ranges('found')[0]
            text_widget.see(first_occurrence)
        else:
            messagebox.showinfo("Search Complete", "Text not found.")
    else:
        messagebox.showinfo("Empty Input", "Please enter text to search for.")

def initialize_context_window(long_text): # Create the main window
    root = tk.Tk()
    root.title("Text Search and Highlight")

    # Create a scrolled text widget
    text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=150, height=80)
    text_widget.pack(padx=10, pady=10)
    text_widget.insert(tk.INSERT, long_text)

    # Highlight tag configuration
    text_widget.tag_config('found', foreground='black', background='yellow')

    # Input for search text
    input_text = tk.StringVar()
    entry = tk.Entry(root, textvariable=input_text)
    entry.pack(side=tk.LEFT, padx=10)

    # Search button
    search_button = tk.Button(root, text="Search and Highlight", command=lambda: search_and_highlight(input_text.get()))
    search_button.pack(side=tk.RIGHT, padx=10)

    # Start the GUI event loop
    root.mainloop()
