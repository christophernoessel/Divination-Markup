from datetime import datetime
import os


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
    # Extract the substring
    substring = original_string[start_index:start_index + length]

    # Build the opening tag with attributes
    opening_tag = f"<{tag_name}"
    for attr_dict in attributes_list:
        for attr_name, attr_value in attr_dict.items():
            opening_tag += f' {attr_name}="{attr_value}"'
    opening_tag += ">"

    # Build the closing tag
    closing_tag = f"</{tag_name}>"

    # Construct the new string
    return original_string[:start_index] + opening_tag + substring + closing_tag + original_string[start_index + length:]

class MarkupManager():
    def __init__(self, file_path):
        
        read_text = read_file_contents(file_path)
        sentences = split_into_sentences(read_text)
        
        self.source_text = source_text
        self.sentence_list = []
        self.sentence_index = 0

    def get_next_sentence():
        self.sentence_index += 1
        if self.sentence_index > len(self.sentence_list):
            return "EOF"
        else:
            return self.sentence_list[sentence_index]

    def get_sentence(index):
        return self.sentence_list[sentence_index]

    def set_index(new_index)

    def my_method(self):
        # Example method that operates on attributes
        print(f"Attribute1: {self.attribute1}, Attribute2: {self.attribute2}")


            

    

if __name__ == "__main__":
    text_data = """
<root>
    <token><token_name>The Curmudgeon</token_name> If you get this, hold on to your hats. It means a hat.</token>
    <token><token_name>Regretful Decline</token_name> Don’t sweat this one as it just means you need a nap.</token>
</root>
"""
    xml_handler = XMLHandler(xml_data)

    for token in xml_handler.tokens:
        print(token.get_text(), token.order, token.token_name)

    token_name = "The Curmudgeon"
    text_to_parse = xml_handler.get_token_text_by_name(token_name)
    to_tag = "a hat"
    start_index = text_to_parse.find(to_tag)
    length = len(to_tag)
    tag_name = "apodosis"
    attributes_list = [{"wn_only": 'fake.n.1, also.n.3'}]
    new_string = tag_substring(text_to_parse, start_index, length, tag_name, attributes_list)

    # Set new text for a token by its name
    xml_handler.set_token_text_by_name(token_name, new_string)

    for token in xml_handler.tokens:
        print(token.get_text(), token.order, token.token_name)
    # Write the modified XML to a file
    now_for_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    xml_handler.write_text(f"output_{now_for_file}.txt")
    
