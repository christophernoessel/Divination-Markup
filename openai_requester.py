import sys
sys.path.append("/Users/chrisrnoessel/Library/Python/3.10/lib/python/site-packages")

import os
import re
from openai import OpenAI

from datetime import date #used in the __main__ example prompt

# IF YOU HAVE AN OPENAI API KEY, INCLUDE IT BELOW
os.environ["OPENAI_API_KEY"] = "<YOUR_API_KEY_HERE>"
# openai.api_key = os.getenv("OPENAI_API_KEY")


try:
    client = OpenAI()
    completion = client.chat.completions.create(
      model="gpt-3.5-turbo",
      messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Test."}
      ]
    )
except:
    client = None
    

def gpt_request(prompt_string):
    if (client == None): return None
    
    awaiting_viable_response = True

    #print(prompt_string)
    
    completion = client.chat.completions.create(
      model="gpt-3.5-turbo",
      messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": f"{prompt_string}"}
      ]
    )

    just_the_content = completion.choices[0].message.content
    return just_the_content


if __name__ == "__main__":
    today = date.today()
    today_string = today.strftime("%B %d")
    example_prompt = f"Name a person who was born on {today_string}?"
    print('Sending the following to chatGPT:\n\n' + example_prompt +'\n\n')

    # Be sure to handle both when chatGPT is available and when it isn’t. You can use this structure.
    response = gpt_request(example_prompt) if (isinstance(client, OpenAI)) else "There was an error accessing GPT"
    
    print(response)
