# CUSTOM CODE
from file_functions             import *
from divmarkup_ask_claude       import *
from divmarkup_text_functions   import *
from divmarkup_wordnet_functions import *
from divmarkup_markup_functions  import *
## from divmarkup_context_window   import *

# UTILITIES
from datetime import date
from datetime import datetime
import sys
import re
import nltk
from nltk.corpus import wordnet as wn
from emoji_text import *

#nltk.download('wordnet')

skip_lines = []

def phase_marker(phase_name):
    match phase_name:
        case 'apodosis':
            lead_char = '❓'
        case 'senses':
            lead_char = '💬'

    print_word_with_emoji(phase_name, lead_char)

def get_unmarked_portion(sentence_text):
    """
    Returns only the portion of text after the last </apodosis> tag.
    If no tags exist, returns the full text.
    """
    last_close_tag = sentence_text.rfind('</apodosis>')
    if last_close_tag == -1:
        return sentence_text
    return sentence_text[last_close_tag + len('</apodosis>'):]

def has_meaningful_content(text):
    """
    Returns True if text contains anything other than whitespace and punctuation.
    """
    # Remove all whitespace and common punctuation
    cleaned = re.sub(r'[\s.,;:!?\'"]+', '', text)
    return len(cleaned) > 0

def main():
    # ==================== START
    now = datetime.now()
    datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(f"Divinatory markup program beginning at {datetime_string}\n\n")

    # get the file to with the text to markup
    print("Please select the file to markup.")
    file_path = select_file() #select a divinatory txt file
    print(f"\n\n opening {file_path} \n\n")

    #file_path = "/Users/christophernoessel/Documents/divination xml/universal_divtext_markup.py/marked_up_i_ching.txt"
    ask_claude = AskClaude() # this manages conversations with Claude
    markup_manager = MarkupManager(file_path) # this holds the text we'll be parsing

    # Where to start?
    start_at = markup_manager.find_last_marked_sentence() #allows us to leave off jobs and return to them later
    start_at += 1 # start with the next one
    number_of_sentences = markup_manager.get_total_sentences()
    print(f"There are {number_of_sentences} sentences in this file.")
    if (start_at >= number_of_sentences):
        print(f"There are apparently no more sentences to process in that file? Congrats?")
        exit()
    
    if start_at > 1:
        print(f"'<apodosis' appears last at {start_at}.")
        response_prompt = f"Do you want to begin processing the file after {start_at}?"
    else:
        response_prompt = "Do you want to begin processing the file at the beginning?"

    while True:
        response = input(f"{response_prompt} y for yes, or a line number.\n")

        if response.lower() == 'y':
            break # go with start_at
        else:
            try:
                num = int(response)
                if (num > number_of_sentences):
                    print(f"That number is too high. Pick one lower than {number_of_sentences}.")
                    continue
                
                if (num < 0):
                    print("That number is too low. Numbers start at 0.")
                    continue
                
                start_at = num
                break
                
            except ValueError:
                print("I did not understand that input. Try again.")


    print(f"starting at {start_at}")

    # ==================== MAIN SENTENCE PROCESSING LOOP

    for x in range(start_at, number_of_sentences):
        
        sentence = markup_manager.get_sentence(x)

        if sentence['parse'] == False:
            print(f"Skipping {x}: {sentence}")
            continue

        # Keep processing the same sentence until user is done with it
        continue_with_sentence = True
        
        while continue_with_sentence:
            # ==================== CLAUDE SUGGESTING APODOSIS
            phase_marker('apodosis')
            
            # Get the latest version of the sentence and only show unmarked portion
            full_sentence = markup_manager.get_sentence(x)['text']
            unmarked_portion = get_unmarked_portion(full_sentence)
            
            # Calculate offset for selection indices (they need to work on full_sentence)
            markup_offset = len(full_sentence) - len(unmarked_portion)
            
            selection_start = selection_end = markup_offset  # Start selections after any existing markup
            
            # ==================== PROMPT/OPPORTUNITY TO MODIFY THE SELECTION
            # In the future this might get moved to something like ApodosisSelectionManager()
            
            finalized_apososis_selection = False
            parse_this_apodosis = False
            pre_add_terms = []  # Terms to pre-add when transitioning to sense phase
            modification_prompt = "\n    [RETURN]:proceed, k:skip, [slice:notation]:substring, c: Claude's suggestion, w:write file"

            while (finalized_apososis_selection == False):
                # displaying ONLY the unmarked portion with suggested apodosis highlighted
                # Calculate indices relative to unmarked_portion for display
                display_start = selection_start - markup_offset
                display_end = selection_end - markup_offset
                
                pre_apodosis = unmarked_portion[:display_start].lower()
                apodosis_uppered = unmarked_portion[display_start:display_end].upper()
                post_apodosis = unmarked_portion[display_end:].lower()
                sentence_with_capitalized_apodosis = pre_apodosis + apodosis_uppered + post_apodosis
                
                print(f" ==================== Confirm: {sentence_with_capitalized_apodosis}\n")

                # prompting for modification
                modify_input = input(modification_prompt +'\n\n')

                if modify_input in ['k', 'skip']: # do nothing
                    print("OK. Skipping this sentence…\n\n")
                    finalized_apososis_selection = True
                    continue_with_sentence = False  # Exit the entire sentence
                    break
                
                elif modify_input == '': # selection is OK as is…
                    print("OK. Running with this apodosis as is…\n\n")
                    finalized_apososis_selection = True
                    parse_this_apodosis = True
                    break
                
                elif modify_input == 'w': # write the file (so work can pause)
                    markup_manager.write_file()

                elif modify_input == 'exit':
                    finalized_apososis_selection = True
                    continue_with_sentence = False
                    break

                elif modify_input == 'c': # this is opt-in since the efficacy is middling and the environmental costs high
                    # Get Claude's suggestion on UNMARKED portion only
                    response_json = ask_claude.recommend_apodosis(unmarked_portion)
                    print(f"response_json: '{response_json}'")
                    
                    if response_json == ask_claude.no_gpt_error_message(): # NO Claude because error or no auth code or offline
                        print('Claude isn’t working, you’ll need to input the phrase or use slice notation for manual selection.')
                        
                    else: # There 
                        # Work with unmarked portion, then adjust indices for full sentence
                        suggested_apodosis = response_json["apodosis"]
                        print(f"\nGiven the sentence: {unmarked_portion}. ", end='')
                        print(f"Claude thinks the apodosis is: {suggested_apodosis}")
                        
                        # Find in unmarked portion, then offset for full sentence
                        local_start = unmarked_portion.find(suggested_apodosis)
                        if local_start != -1:
                            selection_start = local_start + markup_offset
                            selection_end = selection_start + len(suggested_apodosis)
                        else:
                            print(f"Warning: Could not find suggested apodosis in unmarked portion")

                elif len(modify_input) > 1 and modify_input[0] in ['&', '+']:
                    # Check if the arguments are words (not numbers/slice notation)
                    raw_args = modify_input[1:].replace(',', ' ').split()
                    has_word_args = any(not arg.strip().isdigit() for arg in raw_args)
                    if has_word_args:
                        if selection_start == selection_end:
                            print("No apodosis selected yet. Use slice notation to select one first, then add terms.")
                        else:
                            pre_add_terms = [arg.strip() for arg in raw_args if arg.strip()]
                            print(f'Auto-accepting apodosis and pre-adding terms: {pre_add_terms}')
                            finalized_apososis_selection = True
                            parse_this_apodosis = True
                            break
                    else:
                        # Numeric args during apodosis phase - treat as slice notation
                        result_integer, result_string = slice_string_per_content(unmarked_portion, modify_input)
                        match result_integer:
                            case -1:
                                pass
                            case _:
                                selection_start = result_integer + markup_offset
                                selection_end = selection_start + len(result_string)
                        
                else:
                    # User is working with the unmarked portion display, adjust indices
                    result_integer, result_string = slice_string_per_content(unmarked_portion, modify_input)
                    match result_integer:
                        case -1: # error, prompted to try again
                            pass
                        case _: # user entered something and we have to make sure it looks correct
                            # Offset the selection to account for hidden markup
                            selection_start = result_integer + markup_offset
                            selection_end = selection_start + len(result_string)

            if (parse_this_apodosis == False): 
                continue  # Go to next sentence






            # ==================== SELECTING WORDNET SYNSETS
            phase_marker('senses')
            
            confirmed_apodosis = full_sentence[selection_start:selection_end]

            selected_synset_manager = selectedSynsetManager() # a class in divmarkup_wordnet_functions that holds and handles the selection of synsets
            synset_prompt = selected_synset_manager.get_synset_modification_prompt() # instructions for the user

            # Pre-add any terms carried over from the apodosis phase
            if pre_add_terms:
                for term in pre_add_terms:
                    print(f"…pre-adding '{term}'")
                    selected_synset_manager.add_word_with_synsets(term)
                pre_add_terms = []  # Clear after use
                show_list = True  # Show the pre-added terms immediately
            else:
                show_list = False

            while True:
                print(f"{sentence_with_capitalized_apodosis}") #defined above in apodosis selection
                
                if show_list: selected_synset_manager.display() #show the current synsets

                show_list = True # reset it for next time because it should be the default
                modify_selected_synsets = input(synset_prompt) # prompt
                
                result = selected_synset_manager.process_input(modify_selected_synsets, ask_claude, confirmed_apodosis) # SOLICIT INPUT
                
                match result:
                    case 'no_update':
                        show_list = False
                        
                    case 'finalized': # selected synsets are good to go
                        original_string = full_sentence

                        synset_name_list = selected_synset_manager.get_selected_synset_ids()
                        new_sentence = tag_substring(
                            full_sentence,                  # original_string,
                            selection_start,                # start_index,
                            selection_end -selection_start, # length,
                            'apodosis',                     # tag name
                            {'wn_only': synset_name_list},  # attributes_list
                            )

                        markup_manager.set_sentence_text(x, new_sentence)
                        markup_manager.autosave() # yes, every sentence

                        # ==================== CHECK FOR REMAINING TEXT IN SENTENCE
                        # Get the updated sentence after markup
                        full_sentence = markup_manager.get_sentence(x)['text']
                        unmarked_portion = get_unmarked_portion(full_sentence)
                        
                        if has_meaningful_content(unmarked_portion):
                            print(f"\n⚠️  Remaining: {unmarked_portion}\n")
                            # Stay in the sentence loop, go back to apodosis selection
                            continue_with_sentence = True
                        else:
                            # Only whitespace/punctuation remains, move to next sentence
                            continue_with_sentence = False

                        break  # Exit the synset selection loop

                    case _:
                        pass # If the result is neither "no_update" nor "finalized" it will refresh the list above

    file_name = markup_manager.write_file()
    print(f"File written: {file_name}\n")
        
    now = datetime.now()
    datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(f"\n\nCompleted running at {datetime_string}")

if __name__ == "__main__":
    main()