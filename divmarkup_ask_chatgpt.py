from openai_requester import *
import json
import ast

# chatGPT PRE-PROMPTS
# These pre-prompts come in handy when asking chatGPT to do its thing
# finding apodoses and distillation

recommend_apodosis_pre_prompt = """I want you to parse some text to find the phrases that are apodoses.
Understand that these apodoses are divination, and so do not follow the typical "if/then" structure.
Look more for wording that "this" indicates or means or signifies "that."
The "that" will be the apodosis.
When you find it, return a JSON response with the following attributes:
full sentence labeled "full" and just the apodosis labeled "apodosis".
Do not provide an explanation or any other text than the JSON response.
Ignore any text in markup.
Be 'greedy' in that you should find the longest noun phrase that might be the apodosis.
The prior text is instruction.
The sentence I want you to evaluate follows.
"""

# I used to prompt for words, but it added work
recommend_synsets_pre_prompt_WORDS = """I want you to look at an apodosis and
find 3–7 nouns from WordNet that best embody the concepts.
Considering this is divinatory, avoid literal interpretations if possible,
erring on the side of polysemy and applicability to a divinatory reading.
Provide a Python-formatted, single-quoted, comma-separated list of words from Wordnet.
An example is "['progenitor', 'origin', 'first cause']", though this is just an example.
Do not provide an explanation or any other text than the list response.
The prior text are instructions.
The apodosis I want you to evaluate follows.
"""

# This prompts for synset IDs in particular
recommend_synsets_pre_prompt = """I want you to look at an apodosis and
find noun synset IDs from WordNet that best emobdy the concepts.
For example, if the apodosis is "Canis familiaris" the synsetID would be 'dog.n.01'.
This is divinatory, so avoid literal interpretations if possible,
erring on the side of polysemy and applicability to a divinatory reading.
Provide a Python-formatted, single-quoted, comma-separated list of synsetIDs from Wordnet.
An example of response might be "['cat.n.01', 'dog.n.01', 'bird.n.01']".
Do not provide an explanation or any other text than the list response.
Only provide noun synsetIDs that are from the WordNet lexical database.
If the synsetID you have found is for any other part of speech, omit it and find a related noun sysnset.
The prior text are instructions.
The apodosis I want you to evaluate follows.
"""

class AskChatGPT():
    def __init__(self):
        pass

    def no_gpt_error_message(self):
        return 'no_gpt_error_message' # this way it’s clean for outside code to compare/check

    def recommend_apodosis(self, text_to_examine):
        if not (isinstance(client, OpenAI)): return self.no_gpt_error_message()
                
        full_apodosis_prompt = recommend_apodosis_pre_prompt + text_to_examine

        parse_attempts = 3
        while True:
            parse_attempts -= 1
            chatgpt_response = gpt_request(full_apodosis_prompt)
            try:
                response_json = json.loads(chatgpt_response)
            except:
                print(f"Attempt to decode chatGPTs response as a JSON failed. Trying {parse_attempt} more time(s).")
                print(f"full response: {chatgpt_repsonse}")
                if parse_attempts == 0:
                    print("Something must be wrong with chatgpt. Exiting.")
                    exit()
            else:
                return response_json
        
    def modify_apodosis(self):
        # maybe later
        pass
        
    def recommend_synsets(self, apodosis_to_examine):
        if not (isinstance(client, OpenAI)): return self.no_gpt_error_message()
        
        full_synset_prompt = recommend_synsets_pre_prompt + apodosis_to_examine # prepending the control prompt
        
        parse_attempts = 3
        while True:
            parse_attempts -= 1
            chatgpt_response = gpt_request(full_synset_prompt) # getting chatGPT's starting guesses

            try:
                gpt_suggestions = ast.literal_eval(chatgpt_response)
            except:
                print(f"Attempt to decode chatGPTs response with ast failed. Trying {parse_attempt} more time(s).")
                print(f"full response: {chatgpt_repsonse}")
                if parse_attempts == 0:
                    print("Something must be wrong with chatgpt. Exiting.")
                    exit()
            else:
                return gpt_suggestions
                    
    def modify_synsets():
         #maybe later
        pass
