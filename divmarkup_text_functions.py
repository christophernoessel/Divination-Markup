import re
alphabets= "([A-Za-z])"
prefixes = "(Mr|St|Mrs|Ms|Dr)[.]"
suffixes = "(Inc|Ltd|Jr|Sr|Co)"
starters = "(Mr|Mrs|Ms|Dr|He\s|She\s|It\s|They\s|Their\s|Our\s|We\s|But\s|However\s|That\s|This\s|Wherever)"
acronyms = "([A-Z][.][A-Z][.](?:[A-Z][.])?)"
websites = "[.](com|net|org|io|gov)"
import difflib
import string

def tokenized_nouns_in_text(a_text):
    if not(a_text):
        return []
    is_noun = lambda pos: pos[:2] == 'NN'
    tokenized = nltk.word_tokenize(a_text)
    nouns = [word for (word, pos) in nltk.pos_tag(tokenized) if is_noun(pos)]
    
    return nouns

def preprocess(text):
    text = " " + text + "  "
    text = text.replace("\n"," ")
    text = re.sub(prefixes,"\\1<prd>",text)
    text = re.sub(websites,"<prd>\\1",text)
    if "Ph.D" in text: text = text.replace("Ph.D.","Ph<prd>D<prd>")
    text = re.sub("\s" + alphabets + "[.] "," \\1<prd> ",text)
    text = re.sub(acronyms+" "+starters,"\\1<stop> \\2",text)
    text = re.sub(alphabets + "[.]" + alphabets + "[.]" + alphabets + "[.]","\\1<prd>\\2<prd>\\3<prd>",text)
    text = re.sub(alphabets + "[.]" + alphabets + "[.]","\\1<prd>\\2<prd>",text)
    text = re.sub(" "+suffixes+"[.] "+starters," \\1<stop> \\2",text)
    text = re.sub(" "+suffixes+"[.]"," \\1<prd>",text)
    text = re.sub(" " + alphabets + "[.]"," \\1<prd>",text)
    if "”" in text: text = text.replace(".”","”.")
    if "\"" in text: text = text.replace(".\"","\".")
    if "!" in text: text = text.replace("!\"","\"!")
    if "?" in text: text = text.replace("?\"","\"?")
    text = text.replace(".",".<stop>")
    text = text.replace("?","?<stop>")
    text = text.replace("!","!<stop>")
    text = text.replace("<prd>",".")
    return text


def split_into_sentences(text):
    sentences = []

    # If a line in the text is all markup, we don’t need
    # to parse it, but we need it there to write out the file.
    markup_pattern = r'(<[^>]+>|<[^>]+>.*?</[^>]+>)'

    counter = 0
    for this_line in text.splitlines():
##        if counter < 25:
##            print(f'{counter} {this_line}')
        markup_matches = re.findall(markup_pattern, this_line)
        
        if len(markup_matches) > 0:      # it is markup    
            sentence = {}
            sentence["index"] = counter
            sentence["text"]  = this_line
            sentence["parse"] = False # presuming it’s already been done.
            sentences.append(sentence)
            ## if counter < 25: print(sentences[-1])

            counter += 1
            
        else:                            # this is *not* all markup, and may contain multiple sentences
            processed_text = preprocess(this_line)
            split_text = processed_text.split("<stop>")
            if len(split_text) > 1:
                split_text = split_text[:-1] # I think this accounts for the last "<stop>"
            split_text = [s.strip() for s in split_text]

            for each_split in split_text:
                sentence = {}
                sentence["index"] = counter
                sentence["text"]  = each_split
                parse_flag = each_split not in [''] # Don’t parse these
                sentence["parse"] = parse_flag
                sentences.append(sentence)
                ## if counter < 25: print(sentences[-1])

                counter += 1
    
    return sentences


def omit_final_sentence(text):
    sentence_list = split_into_sentences(text)
    if len(sentence_list) == 0:
        return text
    
    sentence_list.pop()
    return_string = " ".join(sentence_list)
    return return_string

def multiple_replace(dict, text):
  # Create a regular expression  from the dictionary keys
  regex = re.compile("(%s)" % "|".join(map(re.escape, dict.keys())))

  # For each match, look-up corresponding value in dictionary
  return regex.sub(lambda mo: dict[mo.string[mo.start():mo.end()]], text)

def contains_list(list_of_sentences):
    for each_sentence in list_of_sentences:
        known_separators = ['!',',',':', ';']
        for this_separator in known_separators:
            as_list = each_sentence.split(this_separator)
            if len(as_list) > 5: #based on subitizeable chunks
                return True
    return False





digression_prefix = '        >>            '
acceptable_strings_list = ["skip", "reenter"]
acceptable_strings = "|".join(item for item in acceptable_strings_list)

def prompt_to_disambiguate_substrings(list_of_possibilities):
    options_display = ''
    
    for x in range(len(list_of_possibilities)):  
        options_display += digression_prefix +str(x) +' ' +list_of_possibilities[x] +'\n'

    while True:
        user_input = input(f"{digression_prefix}Select one or enter [{acceptable_strings}].\n{options_display}")

        if user_input.isdigit() and int(user_input) in range(len(list_of_possibilities)): # Check if input is an integer within the range
            return int(user_input)
            break
        
        elif user_input in acceptable_strings_list: # Check if input is one of the acceptable strings
            return user_input
            break

        else:
            print("Please input a number or command: " )

def find_all_match_indices(main_string, substring):
    pattern = re.compile(substring, re.IGNORECASE)
    return [match.start() for match in re.finditer(pattern, main_string)]

def handle_slicing(main_string, slice_command, part1, part2):
    part1_indices = find_all_match_indices(main_string, part1) if part1 else [0]
    part2_indices = find_all_match_indices(main_string, part2) if part2 else [len(main_string)]

    substrings = []
    for start in part1_indices:
        for end in part2_indices:
            if start < end:
                substring = main_string[start:end + len(part2)]
                substrings.append(substring)

    if len(substrings) == 1:
        return start, substrings[0]
    elif substrings:
        print(f"    '{slice_command}' has multiple possibilities. Disambiguating…")
        intended_substring_index = prompt_to_disambiguate_substrings(substrings)
        start = main_string.find(substrings[intended_substring_index])
        return start, substrings[intended_substring_index]
    else:
        return -1, "No valid substrings found"

def slice_string_per_content(main_string, slice_command):
    # slice a string per content rather than indices
    # returns index where the search term starts, and the substring indicated by the slice_command
    # if there is an error, the index will be -1 and the substring will be that error
    # if user chooses to skip, the index will be -2
    # if user wants to reenter, the index will be -3

    if slice_command == '':
        return -1, "Please include some term to search for in slice notation, e.g. 'hello:world' "
    
    if (":" not in slice_command): # Though not the intended use, it should reply sensibly when looking for "h" in "hello", I guess.
        if slice_command.lower() in main_string.lower():
            matches = re.finditer(slice_command, main_string, re.IGNORECASE)
            indices = [(match.start()) for match in matches]
            
            if len(list(indices)) == 1: # If there’s only one
                starts_at = indices[0]
                return starts_at, slice_command
            else: # If there are multiple, display them in a readable way
                display_string = main_string
                for i in range(len(indices) - 1, -1, -1):
                    start, end = indices[i], indices[i] +len(slice_command)
                    # Replace with ordinal and uppercased version of the substring
                    replacement = f"[{i}]{main_string[start:end].upper()}"
                    display_string = display_string[:start] + replacement + display_string[end:]

                while True:
                    user_input = input(f"There are multiple. Which do you mean? '{display_string}'\n")
                    if user_input.isdigit() and int(user_input) in range(len(indices)): # Check if input is an integer within the range
                        return indices[int(user_input)], slice_command
                        break
                    elif user_input == 'skip':
                        return -2, "User chose to skip"
                    elif user_input == 're-enter':
                        return -3, "User wants to re-enter the term"
                    else:
                        print(f"Select an instance of the found term, or input [{acceptable_strings}]")
        
        else:
            return -1, "The search term is not in the string"
        
    parts_list = slice_command.split(":")

    # Check for errors or special cases
    if len(parts_list) > 2:
        return -1, "Please include only one colon, no stride per https://python-reference.readthedocs.io/en/latest/docs/brackets/slicing.html"
    elif (parts_list[0] == '') and (parts_list[1] == ''):
        return -1, "Please include a term to the right and/or left of the colon."
    
    # Call the generalized function for slicing
    return handle_slicing(main_string, slice_command, *parts_list)


def remove_markup_tags(text):
    """
    Remove all markup tags from the given text.

    Parameters:
    - text: A string that may contain markup tags.

    Returns:
    A string with all markup tags removed.
    """
    # Define a regular expression pattern for markup tags
    # This pattern matches anything that starts with '<', followed by any number of characters that are not '>',
    # and then ends with '>', across multiple lines.
    tag_re = re.compile(r'<[^>]+>', re.MULTILINE)
    
    # Use re.sub() to replace all occurrences of the pattern with an empty string
    return tag_re.sub('', text)


def compare_strings_line_by_line(str1, str2):
    """
    Compare two strings line-by-line and highlight differences.
    
    Parameters:
    - str1: First string to compare.
    - str2: Second string to compare.
    
    Returns:
    A list of tuples, each containing:
    - Line number
    - Line from str1
    - Line from str2
    - Equality marker (True if lines are identical, False otherwise)
    - Detailed differences (if any)
    """
    # Split the strings into lines
    lines1 = str1.strip().split('\n')
    lines2 = str2.strip().split('\n')
    
    # Initialize the result list
    comparison_result = []
    
    # Use difflib to get a detailed line-by-line comparison
    d = difflib.Differ()
    diff = list(d.compare(lines1, lines2))
    
    # Process the diff output to populate the comparison_result
    line_num = 0
    for text in diff:
        code = text[0]
        if code == ' ':  # Lines are identical
            line_num += 1
            comparison_result.append((line_num, text[2:], '', True, ''))
        elif code in ('-', '+'):
            line_num += 1
            line_from_str1 = text[2:] if code == '-' else ''
            line_from_str2 = text[2:] if code == '+' else ''
            # Find detailed difference for the line
            detailed_diff = difflib.ndiff([line_from_str1], [line_from_str2])
            comparison_result.append((line_num, line_from_str1, line_from_str2, False, '\n'.join(detailed_diff)))
    
    return comparison_result


            

if __name__ == "__main__":
    term = "She sells seashells by the seashore"
    print(f"Searching this string: '{term}'")
    for substring in [":she", "she:", "se:se", "", ":", "She:sells:2", "sea", "shore"]:
        result = slice_string_per_content(term, substring)
        print(f"    '{substring}': {result}")
