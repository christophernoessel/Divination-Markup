from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import Synset
import ask_claude
import claude_prompts # data files
import os
import json
from datetime import datetime
import time
import tkinter as tk
from tkinter import filedialog
import re
import sys
from spellchecker import SpellChecker
spell = SpellChecker()

def strip_markup_tags(text):
    return re.sub(r'<[^>]*>', '', text)

def split_text_by_patterns(text, pattern_list):
    result_list = [text]  # Initialize result_list with the original text

    for pattern in pattern_list:
        new_result_list = []  # Create a new list to store the split items for the current pattern

        for item in result_list:
            if re.search(pattern, item):
                # If the item matches the current pattern, split it and add the split items to new_result_list
                matches = re.findall(pattern, item, re.MULTILINE)
                parts = re.split(pattern, item)
                new_result_list.extend([part for sublist in zip(parts, matches + ['']) for part in sublist if part])
            else:
                # If the item doesn't match the current pattern, add it as is to new_result_list
                new_result_list.append(item)

        result_list = new_result_list  # Update result_list with the split items for the current pattern

    # Remove any empty items from the final result_list
    result_list = [item for item in result_list if item.strip()]

    return result_list

def verify_output_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    apodosis_regex = r'<apodosis wn_only="(.*?)">(.*?)</apodosis>'
    apodoses = re.findall(apodosis_regex, content)

    last_vetted_apodosis_file = 'last_vetted_apodosis.txt'
    last_vetted_index = 0

    if os.path.exists(last_vetted_apodosis_file):
        with open(last_vetted_apodosis_file, 'r') as file:
            last_vetted_index = int(file.read().strip())

    # Initialize lemma-sense memory
    lemma_memory = LemmaSenseMemory()

    for index, (synsets, apodosis) in enumerate(apodoses[last_vetted_index:], start=last_vetted_index):
        print(f"\nApodosis {index + 1}:")
        print(f"Sentence: {apodosis}")

        # Parse the synset list
        synset_list = [s.strip() for s in synsets.split(',')]
        
        # Get which synsets should be pre-selected based on memory
        preselected_synsets = lemma_memory.get_selections_for_synset_list(synset_list)
        
        # Group synsets by lemma for adding to manager
        lemma_to_synsets = {}
        for synset_id in synset_list:
            lemma = lemma_memory.extract_lemma_from_synset(synset_id)
            if lemma not in lemma_to_synsets:
                lemma_to_synsets[lemma] = []
            lemma_to_synsets[lemma].append(synset_id)
        
        # Create manager and add words with their remembered selections
        selected_synset_manager = selectedSynsetManager()
        for lemma, lemma_synsets in lemma_to_synsets.items():
            remembered = lemma_memory.get_lemma_senses(lemma)
            # Filter to only synsets that appear in both the current list and memory
            selected = [s for s in lemma_synsets if s in remembered]
            # If no memory exists, add_word_with_synsets will default to first sense
            selected_synset_manager.add_word_with_synsets(lemma, selected)
        
        selected_synset_manager.display()

        while True:
            user_input = input("Enter 'c' to continue, 'm' to modify synsets, or 'q' to quit: ")
            if user_input == 'c':
                # Save current selections to memory before continuing
                selected_ids = selected_synset_manager.get_selected_synset_ids().split(', ')
                
                # Group selected synsets by lemma and save to memory
                for synset_id in selected_ids:
                    lemma = lemma_memory.extract_lemma_from_synset(synset_id)
                    # Get all selected synsets for this lemma
                    lemma_synsets = [s for s in selected_ids 
                                   if lemma_memory.extract_lemma_from_synset(s) == lemma]
                    lemma_memory.set_lemma_senses(lemma, lemma_synsets)
                break
                
            elif user_input == 'm':
                while True:
                    synset_input = input("Enter synset modifications (or 'done' to finish): ")
                    if synset_input == 'done':
                        # Save updated selections to memory
                        selected_ids = selected_synset_manager.get_selected_synset_ids().split(', ')
                        for synset_id in selected_ids:
                            lemma = lemma_memory.extract_lemma_from_synset(synset_id)
                            lemma_synsets = [s for s in selected_ids 
                                           if lemma_memory.extract_lemma_from_synset(s) == lemma]
                            lemma_memory.set_lemma_senses(lemma, lemma_synsets)
                        break
                    selected_synset_manager.process_input(synset_input, None, None)
                    selected_synset_manager.display()
                    
            elif user_input == 'q':
                with open(last_vetted_apodosis_file, 'w') as file:
                    file.write(str(index))
                return

    os.remove(last_vetted_apodosis_file)
    print("Verification completed.")

def get_synset_definition(synset_name):
    # given a synset name, what’s the definition?
    synset = wn.synset(synset_name)
    return synset.definition()

def display_senses(json_data, *selected_list):
    for idx, (key, value) in enumerate(json_data.items(), start=1):
        synset_name = value['synset']
        definition = get_synset_definition(synset_name)
        print(f"{idx}. {synset_name}: {definition}")

def safe_wn_synset(synset_id):
    # claude can return synset IDs that cause deep errors in WordNet,
    # e.g. "celestial_realm.n.01" looks OK but will throw an error.
    # This does the checks it needs to to prevent that.

    # example usage
    # synset = safe_wn_synset("celestial_realm.n.01")
    
    parts = synset_id.split(".")
    if len(parts) != 3       : return []
    if not parts[1] == 'n'   : return [] # This could be made more generally useful with all POS
    if not parts[2].isdigit(): return []
    sense_index = int(parts[2])
    
    synsets = wn.synsets(parts[0], pos=wn.NOUN)
    for synset in synsets:
        if synset.name() == synset_id:
            return synset
    return False    

def most_primary_sense_lemmas_for(synset_id):
    # Any given synset id that comes from claude
    # needs to be added to the selection.
    # But since there is a many:many relationship there,
    # we only want to go with the words/lemmas for
    # which this synset is more-primary to that lemma
    # than others. This hard-won function identifies
    # those lemmas and returns their names() in a list.

    target_synset = safe_wn_synset(synset_id)  # Retrieve the synset object for the given synset ID
    if not target_synset: return []

    my_lemmas = target_synset.lemmas()  # Retrieve all lemmas associated with the target synset
    lowest_index = sys.maxsize  # Initialize lowest_index with the largest integer value
    lemma_list = []  # Initialize an empty list to store the lemmas with the lowest index

    for lemma in my_lemmas:  # Iterate through each lemma of the target synset
        lemma_name = lemma.name()  # Get the name of the lemma
        # Retrieve all synsets of this lemma (filtered by the POS of the target synset)

        try:
            lemma_synsets = wn.synsets(lemma_name, pos=target_synset.pos())
        except wn.WordNetError:
            print(f"Warning: No lemma '{lemma_name}' with part of speech '{target_synset.pos()}'. Moving on…")
            continue

        if target_synset in lemma_synsets:  # Check if the target synset is in the lemma's synset list
            this_index = lemma_synsets.index(target_synset)  # Find the index of the target synset
            if this_index < lowest_index:  # If this index is the lowest so far
                lowest_index = this_index  # Update the lowest index
                lemma_list = [lemma_name]  # Reset the lemma list with the current lemma
            elif this_index == lowest_index:  # If this index is equal to the current lowest index
                lemma_list.append(lemma_name)  # Add the lemma to the lemma list

    return lemma_list  # Return the list of lemmas with the lowest index for the target synset

class LemmaSenseMemory:
    """Manages persistent memory of lemma-sense selections."""
    
    def __init__(self, filepath='lemma_sense_memory.json'):
        self.filepath = filepath
        self.memory = self._load_memory()
    
    def _load_memory(self):
        """Load existing memory from file, or return empty dict."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_memory(self):
        """Persist memory to file."""
        with open(self.filepath, 'w') as f:
            json.dump(self.memory, f, indent=2)
    
    def get_lemma_senses(self, lemma):
        """Get previously selected senses for a lemma.
        Returns list of synset IDs, or empty list if lemma not in memory."""
        return self.memory.get(lemma, [])
    
    def set_lemma_senses(self, lemma, synset_ids):
        """Store selected senses for a lemma.
        synset_ids should be a list of synset ID strings."""
        self.memory[lemma] = list(synset_ids)  # Ensure it's stored as a list
        self.save_memory()
    
    def extract_lemma_from_synset(self, synset_id):
        """Extract lemma name from synset ID (e.g., 'dog.n.01' -> 'dog')."""
        return synset_id.split('.')[0]
    
    def get_selections_for_synset_list(self, synset_ids):
        """Given a list of synset IDs, return which ones should be pre-selected
        based on memory. Returns a list of synset IDs to select."""
        selections = []
        for synset_id in synset_ids:
            lemma = self.extract_lemma_from_synset(synset_id)
            remembered = self.get_lemma_senses(lemma)
            if synset_id in remembered:
                selections.append(synset_id)
        return selections

class selectedSynsetManager:
    def __init__(self):
        self.wordnet_data = {}
        self.show_deselected = True
        self.display_number_to_synset = {}  # Mapping display numbers to synsets, allows easy control
        self.output_outdent = '    '
        self.lemma_memory = LemmaSenseMemory()

    # CONSTANTS
    def no_update(self):
        return 'no_update'

    # MANAGING WORDS AND SYNSETS
    def create_dict_with_words(self, words):
        for word in words:
            self.add_word_with_synsets(word)

    def create_dict_with_synsetids(self, synset_ids):
        if not isinstance(synset_ids, list):
            print(f"{synset_ids} is not a list.")
            return
        
        for synset_id in synset_ids:
            synset = safe_wn_synset(synset_id)
            if synset:
                primary_words = most_primary_sense_lemmas_for(synset_id)
                for primary_word in primary_words:
                    self.add_word_with_synsets(primary_word, [synset_id])
            else:
                print(f"Synset ID '{synset_id}' not found in WordNet.")

    def check_spelling(self, word):
        results = wn.synsets(word)
        if len(results) > 0:
            return word
        else:
            alt_word = spell.correction(word)
            if alt_word is None:
                print(f'I could not find anything for "{word}" and spellchecker could not suggest an alternate spelling.')
                return None
            else:
                results = wn.synsets(alt_word)
                if len(results) == 0:
                    print(f'Neither "{word}" nor spellchecker’s recommendation "{alt_word}" returned results.')
                    return None
                else:
                    print(f'I could not find anything for "{word}" but did find something for "{alt_word}".')
                    return alt_word
            

    def add_word_with_synsets(self, word, selected_synsets = []):
        word = self.check_spelling(word)
        if word is None: return
        
        synsets = wn.synsets(word, pos = wn.NOUN)
        self.wordnet_data[word] = {}

        # This should save time by preselecting senses for this lemma that have been selected before
        if len(selected_synsets) == 0:
            selected_synsets = self.lemma_memory.get_lemma_senses(word)
        
        for i, synset in enumerate(synsets):
            if len(selected_synsets) > 0:
                #print(f"{i} {synset} from {selected_synsets}")
                selected_state = True if synset.name() in selected_synsets else False
            else:
                selected_state = True if i == 0 else False
            
            self.wordnet_data[word][synset.name()] = {'selected': selected_state}        

    def delete_word(self, word):
        if word in self.wordnet_data:
            del self.wordnet_data[word]
        else:
            return 'word not found'

    def set_synset_selection(self, synset_name, to_status):
        for word, synsets in self.wordnet_data.items():
            #print(f"word:{word}, synset_name: {synset_name}, synsets: {synsets}")
            if synset_name in synsets:
                #print(f"self.wordnet_data[word][synset_name]['selected']: {self.wordnet_data[word][synset_name]['selected']}")
                self.wordnet_data[word][synset_name]['selected'] = to_status
                #print(f"self.wordnet_data[word][synset_name]['selected']: {self.wordnet_data[word][synset_name]['selected']}")
                # return # it’s tempting to return here, but many words can have the same synset, so we need to turn them all off 

    # GETTING DATA OUT
    def get_wordnet_data(self): #all the data (not sure when you’d use this)
        return self.wordnet_data

    def get_synset_modification_prompt(self):
        return "[ENTER]:OK. +/-:(de)select number/range/word, ?:lookup, s:synonyms, &|x: add/delete word+synsets, /:toggle deselected, c: ask Claude \n\n"

    def get_synset_by_display_number(self, display_number): # user-supplied controls
        #print(f"display_number: {display_number}, display_number in self.display_number_to_synset: {display_number in self.display_number_to_synset}, self.display_number_to_synset: {self.display_number_to_synset}")
        if display_number in self.display_number_to_synset:
            word, synset_name = self.display_number_to_synset[display_number]
            #print(f"word: {word}, synset_name: {synset_name}, wn.synset(synset_name): {wn.synset(synset_name)}")
            synset = safe_wn_synset(synset_name)  # Retrieve the actual synset object
            return synset
        else:
            print(f"Display number {display_number} not found.")
            return None

    def get_selected_synset_ids(self): # this is used for the XML markup
        selected_ids = set()
        for word, synsets in self.wordnet_data.items():
            for synset_name, info in synsets.items():
                if info['selected']:
                    selected_ids.add(synset_name)
        return ', '.join(selected_ids) #this returns a string
        #return selected_ids
    
    # DISPLAY CONTROL
    def toggle_show_selected(command = 'toggle'):
        self.show_deselected = command if (command in [True,False]) else (not self.show_deselected)

    def display(self):
        counter = 0
        self.display_number_to_synset.clear()
        for word, synsets in self.wordnet_data.items():
            print(word.upper())  # Print the word in all-caps
            for synset_name, info in synsets.items():
                if ((self.show_deselected == False) and (info['selected'] == False)): continue
                status_symbol = "✅" if info['selected'] else "❌"
                synset = wn.synset(synset_name)
                definition = synset.definition()
                print(f"{self.output_outdent}{counter}. {status_symbol} {synset_name}: {definition}")
                self.display_number_to_synset[counter] = (word, synset_name)
                counter += 1

    # USER COMMANDS

    def process_input(self, input_string, ask_claude, apodosis_for_claude):
            if input_string == '':
                control_character = oddment = '' 
            else:               
                control_character = input_string[0]
                oddment = input_string[1:] if len(input_string) > 1 else ''

                # First, extract and handle quoted strings
                quoted_strings = re.findall(r'"([^"]*)"', oddment)
                # Remove the quoted strings from the oddment
                oddment = re.sub(r'"([^"]*)"', '', oddment)

                # Now, handle the non-quoted parts (like numbers and ranges)
                non_quoted_parts = oddment.replace(',', ' ').split()

                # Combine both quoted and non-quoted parts
                control_list = quoted_strings + non_quoted_parts

            # Multi-operator parsing handles +/- with mixed word and number args below.

            match control_character:
                case '': # Looks good as is, move on
                    if len(self.get_selected_synset_ids()) == 0:
                        print("\nNo senses are selected. Please select some words/synsets.\n")
                        return
                    else:
                        print("OK, marking up the apodosis with these synsets…")
                        self._save_current_selections_to_memory() # save this for later reference
                        return 'finalized'
                    
                case '/': # toggle show_deselected
                    current_state = self.show_deselected
                    new_states = ['showing', 'hide'] if current_state == True else ['hiding','show']
                    print(f"I was {new_states[0]} deselected but now I will {new_states[1]} deselected.")
                    self.show_deselected = not self.show_deselected
                    return

                case 'x': #delete word and all its synsets
                    for word in control_list:
                        result = self.delete_word(word.strip())
                        if result == 'word not found':
                            print (f'{word} not found…')
                        
                    print('Ran delete_word…')
                    return

                case '+' | '-': # select/deselect, add/delete — supports mixed operators
                    # Parse the full input into operator groups
                    # e.g. "+ 1 3:5 - 7 + term1 - term3"
                    # → [('+', ['1', '3:5']), ('-', ['7']), ('+', ['term1']), ('-', ['term3'])]
                    groups = self._parse_operator_groups(input_string)
                    
                    for op, args in groups:
                        # Classify args as words vs numeric
                        word_args = []
                        numeric_args = []
                        for arg in args:
                            stripped = arg.strip()
                            is_keyword = stripped.lower() == 'all'
                            is_pure_number = stripped.isdigit()
                            is_numeric_range = bool(re.match(r'^\d+[–—:…]\d+$', stripped))
                            if is_keyword or is_pure_number or is_numeric_range:
                                numeric_args.append(stripped)
                            else:
                                word_args.append(stripped)
                        
                        # Handle word args: + → add word, - → delete word
                        if word_args:
                            if op == '+':
                                for word in word_args:
                                    print(f"…adding '{word}'")
                                    self.add_word_with_synsets(word)
                            else:  # op == '-'
                                for word in word_args:
                                    result = self.delete_word(word)
                                    if result == 'word not found':
                                        print(f'{word} not found…')
                                    else:
                                        print(f"…removed '{word}'")
                        
                        # Handle numeric args: select/deselect synsets by display number
                        if numeric_args:
                            synset_list = self._resolve_synsets_from_numeric_args(numeric_args)
                            status_to_set = True if op == '+' else False
                            for each_synset in synset_list:
                                self.set_synset_selection(each_synset.name(), status_to_set)
                    
                case '?': # lookup (word or synsetID)
                    print(f"Looking up {control_list}…")
                    
                    for each_word in control_list:
                        
                        print(f"WordNet LOOKUP for {each_word.upper()}")
                        
                        synsets = wn.synsets(each_word.strip(), pos = wn.NOUN)
                        
                        if not synsets:
                            print("There are no synsets for this word?")
                        else:
                            for synset in synsets:
                              print(f"{self.output_outdent}{synset.name()}: {synset.definition()}")
                            print('\n')
                              
                    return self.no_update()

                case '&': # add word and its synsets
                    for each_word in control_list:
                        print(f"…adding '{each_word.strip()}'")
                        self.add_word_with_synsets(each_word.strip())

                case 's': # list synonyms for word
                    for each_word in control_list:
                        synonym_list_list = wn.synonyms(each_word)
                        flat_list = [item for sublist in synonym_list_list for item in sublist]
                        as_string = ', '.join(flat_list)
                        print(f"synonyms for {each_word}: {as_string}\n")
                        return self.no_update()
                    
                case 'c': # ask claude is opt-in for efficacy and environmental concerns
                    gpt_suggestions = ask_claude.recommend_synsets(apodosis_for_claude) # Get Claude’s suggestion
                    if gpt_suggestions == ask_claude.no_gpt_error_message(): # NO gpt…
                        synset_prompt = f'Claude did not provide any responses. (Or may be broken?)'
                    else:
                        print(f"Claude suggests: {gpt_suggestions}")
                        print(self.no_update())

                case _:
                    print('I did not recognize this input.')
                    return self.no_update()   
                
    def _parse_operator_groups(self, input_string):
        """Parse input like '+ 1 3:5 - 7 + term1 - term3' into operator groups.
        Returns list of (operator, [args]) tuples.
        Handles quoted strings as single args."""
        groups = []
        current_op = None
        current_args = []
        
        # Tokenize respecting quoted strings
        # First, replace quoted strings with placeholders
        quoted = re.findall(r'"([^"]*)"', input_string)
        temp = re.sub(r'"[^"]*"', '\x00QUOTED\x00', input_string)
        tokens = temp.replace(',', ' ').split()
        
        # Restore quoted strings
        quote_idx = 0
        for i, token in enumerate(tokens):
            if '\x00QUOTED\x00' in token:
                tokens[i] = quoted[quote_idx]
                quote_idx += 1
        
        for token in tokens:
            if token in ['+', '-']:
                # Save previous group if any
                if current_op is not None and current_args:
                    groups.append((current_op, current_args))
                current_op = token
                current_args = []
            elif current_op is None:
                # First token is the operator character (e.g., "+3" → op='+', arg='3')
                if token[0] in ['+', '-']:
                    current_op = token[0]
                    if len(token) > 1:
                        current_args.append(token[1:])
                else:
                    current_op = '+'  # default
                    current_args.append(token)
            else:
                current_args.append(token)
        
        # Don't forget the last group
        if current_op is not None and current_args:
            groups.append((current_op, current_args))
        
        return groups

    def _resolve_synsets_from_numeric_args(self, numeric_args):
        """Given a list of numeric strings and ranges, resolve to synset objects.
        Range characters: – — : … (not -, which is now reserved as an operator)."""
        range_characters = ['–', '—', ':', '…']
        normalize_char = ':'
        synset_list = []
        
        for each_string in numeric_args:
            is_range = any(ch in each_string for ch in range_characters)
            
            if each_string.strip().lower() == 'all':
                for word, synsets in self.wordnet_data.items():
                    for synset in synsets.keys():
                        synset_list.append(safe_wn_synset(synset))
            
            elif not is_range:  # simple number
                try:
                    as_int = int(each_string)
                    result_object = self.get_synset_by_display_number(as_int)
                    if isinstance(result_object, Synset):
                        synset_list.append(result_object)
                except ValueError:
                    print(f"'{each_string}' is not a valid number.")
            
            else:  # range like 3:7 or 3…7
                display_string = each_string
                for char in range_characters:
                    display_string = display_string.replace(char, normalize_char)
                
                endcap_list = display_string.split(normalize_char)
                
                if len(endcap_list) != 2:
                    print(f"Range '{each_string}' is malformed. Use one separator between two numbers.")
                    continue
                
                try:
                    start_int = int(endcap_list[0])
                    end_int = int(endcap_list[1])
                except ValueError:
                    print(f"Range '{each_string}' contains non-numeric endcaps. Skipping.")
                    continue
                
                if start_int >= end_int:
                    print(f"The endcaps in '{each_string}' are not ascending. Skipping.")
                    continue
                
                for x in range(start_int, end_int + 1):
                    result_object = self.get_synset_by_display_number(x)
                    if isinstance(result_object, Synset):
                        synset_list.append(result_object)
        
        return synset_list

    def _save_current_selections_to_memory(self):
        """Save currently selected synsets to memory, grouped by lemma."""
        selected_ids = self.get_selected_synset_ids().split(', ')
        
        # Group by lemma
        lemma_to_synsets = {}
        for synset_id in selected_ids:
            lemma = self.lemma_memory.extract_lemma_from_synset(synset_id)
            if lemma not in lemma_to_synsets:
                lemma_to_synsets[lemma] = []
            lemma_to_synsets[lemma].append(synset_id)
        
        # Save each lemma's selections
        for lemma, synset_list in lemma_to_synsets.items():
            self.lemma_memory.set_lemma_senses(lemma, synset_list)          

if __name__ == "__main__":
    pass
##    selected_synset_manager = selectedSynsetManager()
##    selected_synset_manager.create_dict_with_words(['cat', 'dog'])
##    selected_synset_manager.display()
##    
##    command_list = ['-all', '+ all', '- 0-7', '+0 6', '- 8:10, 12:14, 11',
##                    '/', '+ 8', '/', '+8', '/', 'x cat', '/', '? mouse house "first cause"', '& mouse']
##    for command in command_list:
##        print(f"\n\nexecuting command '{command}'")
##        result = selected_synset_manager.process_input(command)
##        if (result) != 'no update': selected_synset_manager.display()