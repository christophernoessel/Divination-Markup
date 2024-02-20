import nltk
from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import Synset
#nltk.download('wordnet')
import re
import sys
from spellchecker import SpellChecker
spell = SpellChecker()

# WORDNET FUNCTIONS
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
    # chatGPT can return synset IDs that cause deep errors in WordNet,
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
    # Any given synset id that comes from chatGPT
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


class selectedSynsetManager:
    def __init__(self):
        self.wordnet_data = {}
        self.show_deselected = True
        self.display_number_to_synset = {}  # Mapping display numbers to synsets, allows easy control
        self.output_outdent = '    '


    # CONSTANTS
    def no_update(self):
        return 'no_update'

    # MANAGING WORDS AND SYNSETS
    def create_dict_with_words(self, words):
        for word in words:
            self.add_word_with_synsets(word)

    def create_dict_with_synsetids(self, synset_ids):
        if not isinstance(synset_ids, list):
            print(f"{synsetids} is not a list.")
            return
        
        for synset_id in synset_ids:
            primary_words = most_primary_sense_lemmas_for(synset_id)
            for primary_word in primary_words:
                self.add_word_with_synsets(primary_word, [synset_id])

    def check_spelling(self, word):
        results = wn.synsets(word)
        if len(results) > 1:
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
        
        for i, synset in enumerate(synsets):
            if len(selected_synsets) > 0:
                #print(f"{i} {synset} from {selected_synsets}")
                selected_state = True if synset.name() in selected_synsets else False
            else:
                selected_state = True if i == 0 else False
            
            # Set 'selected' to True for the first synset, False for others
            self.wordnet_data[word][synset.name()] = {'selected': selected_state}

            # print(f"self.wordnet_data: {self.wordnet_data}\n\n")
        

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
        return "[ENTER]:OK. -|+:(de)select number/range, ?:lookup, s:synonyms, &|x: add/delete word+synsets, /:toggle deselected, g: ask chatGPT \n\n"

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

    def process_input(self, input_string, ask_chatgpt, apodosis_for_chatGPT):
            if input_string == '':
                control_character = oddment = '' 
            else:
##                control_character = input_string[0]
##                oddment = input_string[1:] if len(input_string) > 1 else ''
##                control_list = oddment.replace(',', ' ').split() # note this will be a list of strings
                
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
        
            match control_character:
                case '': # Looks good as is, move on
                    print("OK, marking up the apodosis with these synsets…")
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

                case '+' | '-': # select or deselect
                    #print("I see you wish to +- something")
                    synset_list = []
                    
                    for each_string in control_list: #Convert the strings to a list of synsets in the object
                        
                        range_characters = ['-', '–', '—', ':', '…']
                        dash_char = '-'
                        is_range = any(character in each_string for character in range_characters) # does the string contain one of range_characters?
                        
                        if each_string.strip() == 'all': # a keyword that affects all synsets. Very powerful without undo.
                            all_synsets = []
                            for word, synsets in self.wordnet_data.items():
                                for synset in synsets.keys():
                                    synset_list.append(safe_wn_synset(synset))
##                            print(f"synset_list: {synset_list}")                                
                            
                        elif not is_range:  # not a range, the simple case 
                            as_int = int(each_string)
                            result_object = self.get_synset_by_display_number(as_int)
                            if isinstance(result_object, Synset): # then it’s a synset
                                synset_list.append(result_object)
                                
                        elif is_range:    # user has indicated a range
                            display_string = each_string # making a copy because we are modifying it
                            for char in range_characters:
                                display_string = display_string.replace(char, dash_char) # simplifying for split

                            endcap_list = display_string.split(dash_char)

                            # TO DO This should account for slice syntax, e.g. 3: and :3
                            if len(endcap_list) != 2: # typo of some sort
                                print(f"endcap_list: {endcap_list}")
                                print("When specifying a range, have one number to the left and one to the right of the range character. No changes have been made.")
                                return

                            synset_endcap_integer_list = []
                            
                            for each_number_string in endcap_list: # only 2, but we need to check each
                                # print(f"each_number_string: {each_number_string}")
                                as_int = int(each_number_string)
                                if isinstance(as_int, int):
                                    synset_endcap_integer_list.append(as_int)
                                else:
                                    print(f"One of the endcaps you provided in a range, '{each_number_string}', is not an int. Not executing.")
                                    return

                            if synset_endcap_integer_list[0] >= synset_endcap_integer_list[1]:
                                print(f"The endcaps in '{each_string}' are not ascending, so probably an error? Not executing.")
                                return
                            
                            for x in range(synset_endcap_integer_list[0], (synset_endcap_integer_list[1]) +1):
                                # print(f"adding synset number {x}…")
                                result_object = self.get_synset_by_display_number(x)
                                if isinstance(result_object, Synset):
                                    synset_list.append(result_object)

                    status_to_set = True if control_character == '+' else False
                    for each_synset in synset_list:
                        #print(f"setting {each_synset} to {status_to_set}.")
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
                    
                case 'g': # ask chatGPT is opt-in for efficacy and environmental concerns
                    gpt_suggestions = ask_chatgpt.recommend_synsets(apodosis_for_chatGPT) # Get chatGPT’s suggestion
                    if gpt_suggestions == ask_chatgpt.no_gpt_error_message(): # NO gpt…
                        synset_prompt = f'chatGPT did not provide any responses. (Or may be broken?)'
                    else:
                        print(f"chatGPT suggests: {gpt_suggestions}")
                        print(self.no_update())

                case _:
                    print('I did not recognize this input.')
                    return self.no_update()             

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


    
        


