from datetime                   import datetime
from divmarkup_text_functions   import *
from file_functions             import *
import os
import re
import difflib

date_suffix_re_pattern = r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"

def get_root_filename(file_path):
    # Extract the base name of the file (e.g., 'example.txt' from '/path/to/example.txt')
    base_name = os.path.basename(file_path)
    
    # Split the base name into root name and extension and return the root name
    root_name, _ = os.path.splitext(base_name)
    
    # Exclude the dot-three file extension (last three characters) if it exists
    if len(root_name) > 3 and root_name[-4] == '.':
        return root_name[:-4]
    else:
        return root_name

def tag_substring(original_string, start_index, length, tag_name, attributes_list):
##    params = locals()
##    print("Function parameters and their values:")
##    for param, value in params.items():
##        print(f"{param}: {value}")
        
    # Extract the substring
    substring = original_string[start_index:start_index + length]

    # Build the opening tag with attributes
    opening_tag = f"<{tag_name}"
    for attr_name, attr_value in attributes_list.items():
        opening_tag += f' {attr_name}="{attr_value}"'
    opening_tag += ">"

    # Build the closing tag
    closing_tag = f"</{tag_name}>"

    # Construct the new string
    return original_string[:start_index] + opening_tag + substring + closing_tag + original_string[start_index + length:]

class MarkupManager():
    def __init__(self, file_path):
        self.source_path = file_path
        self.source_text = read_file_contents(self.source_path)
        
        self.sentences = split_into_sentences(self.source_text)
        # sentences is a list, each entry a dict with index, parse flag, and text
        ## print('\n\n')
        ## print(self.sentences[:25])
        ## write_dicts_to_file(self.sentences) # this was for debugging.
##        for x in range(58):
##            print(f"initialized {x} {self.sentences[x]['text']}")
        
        self.sentence_index = 0
        
        datetime_suffix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.autosave_filename = f"divmarkup_autosave_session_{datetime_suffix}.xml" 

    def find_last_marked_sentence(self):
        for index in range(len(self.sentences) - 1, -1, -1):
            sentence = self.sentences[index]['text']
##            if index < 58: print(f"{index} {'<apodosis' in sentence}: {sentence}")
            if '<apodosis' in sentence:
                return index  # Return immediately when a marked sentence is found
        return 0  # Return 0 if no marked sentence is found

    def get_total_sentences(self):
        return len(self.sentences)

    def get_sentence(self, sentence_index):
        return self.sentences[sentence_index]

    def set_sentence_text(self, sentence_index, new_text):
        if len(self.sentences) < sentence_index < 0:
            return "Index out of range"
        self.sentences[sentence_index]['text'] = new_text
        return self.sentences[sentence_index]

    def autosave(self):
        self.write_file(True)

    def write_file(self, is_autosave=False):
        datetime_suffix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename, file_extension = os.path.splitext(self.source_path)

        if is_autosave:
            new_filename = self.autosave_filename
        else:
            filename = re.sub(date_suffix_re_pattern, '', filename) # strip any existing date stamp
            new_filename = f"{filename}_{datetime_suffix}.xml"
        
        contents = ""
        for sentence in self.sentences:
            contents += f"{sentence['text']}\n"
            
        with open(new_filename, 'w') as file:
            file.write(contents) # this completely overwrites existing content
        self.last_written_file = new_filename
        
        if not is_autosave: print(f"{new_filename} written.")
        return new_filename
    

if __name__ == "__main__":
    pass