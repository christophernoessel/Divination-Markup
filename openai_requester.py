import sys
sys.path.append("/Users/chrisrnoessel/Library/Python/3.10/lib/python/site-packages")

import os
import re
from openai import OpenAI

from datetime import date #used in the __main__ example prompt

os.environ["OPENAI_API_KEY"] = "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"
#openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()

def gpt_request(prompt_string):
    awaiting_viable_response = True

    #print(prompt_string)
    
    completion = client.chat.completions.create(
      model="gpt-3.5-turbo",
      messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": f"{prompt_string}"}
      ]
    )

    #print(completion)
    #print('\n\n')
    just_the_content = completion.choices[0].message.content
    return just_the_content

# print(completion.choices[0].message)



if __name__ == "__main__":
    today = date.today()
    today_string = today.strftime("%B %d")
    example_prompt = f"Name a person who was born on {today_string}?"
    print('Sending the following to chatGPT:\n\n' + example_prompt +'\n\n')
    response = gpt_request(example_prompt)
    print(response)
    #pass
