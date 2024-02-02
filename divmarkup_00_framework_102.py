# CUSTOM CODE
from file_functions             import *
from divmarkup_ask_chatgpt      import *
from divmarkup_text_functions   import *
from divmarkup_wordnet_fuctions import *
from divmarkup_markup_fuctions  import *

# UTILITIES
from datetime import date
from datetime import datetime
import sys
import re
import nltk
from nltk.corpus import wordnet as wn
#nltk.download('wordnet')


def main():
    # ==================== START
    now = datetime.now()
    datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(f"Divinatory markup program beginning at {datetime_string}\n\n")

    # get the file to with the text to markup
    print("Please select the file to markup.")
    file_path = select_file() #select a divinatory txt file

    #file_path = "/Users/christophernoessel/Documents/divination xml/universal_divtext_markup.py/marked_up_i_ching.txt"
    ask_chatgpt = AskChatGPT() # this manages conversations with chatGPT
    markup_manager = MarkupManager(file_path) # this holds the text we’ll be parsing

    # Where to start?
    start_at = markup_manager.find_last_marked_sentence() #allows us to leave off jobs and return to them later
    number_of_sentences = markup_manager.get_total_sentences()
    
    if start_at > 0:
        print(f"There are {number_of_sentences} sentences in this file. '<apodosis' appears last at {start_at}.")
        response = input(f"Do you want to begin processing the file after {start_at}? y/n\n")
        if response == 'n': start_at = 0

    # ==================== CHATGPT SUGGESTING APODOSIS

    if (start_at >= number_of_sentences):
        print(f"There are apparently no more sentences to process in that file.")
        exit()

    for x in range(start_at, number_of_sentences):
        sentence = markup_manager.get_sentence(x)
        
        # Get chatGPT’s suggestion
        response_json = ask_chatgpt.recommend_apodosis(sentence)
        
        full_sentence      = response_json["full"] # things get weird if the response doesn't match input
        if full_sentence  != sentence:
            print(f"chatGPT returned {full_sentence} for {sentence}, and that ain’t right. Not sure what to do.")
                    
        print(f"\nGiven the sentence: {full_sentence}")
        suggested_apodosis = response_json["apodosis"] #variable names, e.g. “apodosis" are specified in the pre_prompt
        print(f"I think the apodosis is: {suggested_apodosis}")
        selection_length    = len(suggested_apodosis)
        selection_start     = full_sentence.find(suggested_apodosis)
        
        if (selection_start == -1):
            print("Python could not find the apodosis chatGPT says it found, so not showing anything")
            selection_start = selection_end = 0
        else:
            selection_end   = selection_start +selection_length

        # ==================== OPPORTUNITY TO MODIFY THE SELECTION
        # In the future this might get moved to something like ApodosisSelectionManager()
        
        finalized_apososis_selection = False
        parse_this_apodosis = False
        modification_prompt = "\n    [RETURN] = proceed. k = skip. [slice:notation] substring. w = write file"

        while (finalized_apososis_selection == False):
            # displaying the sentence with the suggested apodosis in uppercase for easy human parsing
            pre_apodosis        = full_sentence[:selection_start].lower()
            apodosis_as_indexed = full_sentence[selection_start:selection_end]
            apodosis_uppered    = apodosis_as_indexed.upper()
            post_apodosis       = full_sentence[selection_end:].lower()
            sentence_with_capitalized_apodosis = pre_apodosis +apodosis_uppered +post_apodosis
            
            print(f"Confirm: {sentence_with_capitalized_apodosis}\n")

            # prompting for modification
            modify_input = input(modification_prompt +'\n\n')

            if modify_input in ['k', 'skip']: # do nothing
                print("OK. Skipping this sentence…\n\n")
                finalized_apososis_selection == True
                break
            
            elif modify_input == '': # selection is OK as is…
                print("OK. Running with this apodosis as is…")
                finalized_apososis_selection == True
                parse_this_apodosis = True
                break
            
            elif modify_input == 'w': # write the file (so work can pause)
                markup_manager.write_file()
                
            else:
                result_integer, result_string = slice_string_per_content(full_sentence, modify_input)
                match result_integer:
                    case -1: # error, prompted to try again
                        pass
                    case _: # user entered something and we have to make sure it looks correct
                        selection_start = result_integer
                        selection_end   = result_integer +len(result_string)

        if (parse_this_apodosis == False): continue

        
        # ==================== SELECTING WORDNET SYNSETS
        confirmed_apodosis = full_sentence[selection_start:selection_end]

        gpt_suggestions = ask_chatgpt.recommend_synsets(confirmed_apodosis) # Get chatGPT’s suggestion

        selected_synset_manager = selectedSynsetManager() # a class in divmarkup_wordnet_functions that holds and handles the selection of synsets
        selected_synset_manager.create_dict_with_synsetids(gpt_suggestions) # initialize the words
        show_list = True # lookups shouldn’t re-show the list, so this allows control
        synset_prompt = selected_synset_manager.get_synset_modification_prompt()

        while True:
            print(f"{sentence_with_capitalized_apodosis}") #defined above in apodosis selection
            if show_list: selected_synset_manager.display() #show the current synsets
            show_list = True # reset because it should be the default

            modify_selected_synsets = input(synset_prompt) # prompt
            
            result = selected_synset_manager.process_input(modify_selected_synsets)
            
            match result:
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

                    markup_manager.set_sentence(x, new_sentence)
                    markup_manager.autosave()
                    break

    file_name = markup_manager.write_file()
    print(f"File written: {file_name}\n")
        
    now = datetime.now()
    datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(f"\n\nCompleted running at {datetime_string}")

if __name__ == "__main__":
    main()