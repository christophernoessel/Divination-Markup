import anthropic
import json
import ast
import os

# Claude PRE-PROMPTS
# These pre-prompts come in handy when asking Claude to do its thing
# finding apodoses and distillation

recommend_apodosis_pre_prompt = """I want you to parse some text to find the phrases that are apodoses.
Understand that these apodoses are divination, and so do not follow the typical "if/then" structure.
Look more for wording that "this" indicates or means or signifies "that."
The "that" will be the apodosis.
When you find it, return a JSON response with the following attributes:
full sentence labeled "full" and just the apodosis labeled "apodosis".

CRITICAL: Return ONLY the raw JSON object. Do NOT wrap it in markdown code blocks, backticks, or any other formatting.
Do NOT include ```json or ``` in your response.
Do NOT provide any explanation, preamble, or text other than the raw JSON.
Your response must start with { and end with }.

Ignore any text in markup.
Be 'greedy' in that you should find the longest noun phrase that might be the apodosis.
The prior text is instruction.
The sentence I want you to evaluate follows.
"""

# This prompts for synset IDs in particular
recommend_synsets_pre_prompt = """I want you to look at an apodosis and
find noun synset IDs from WordNet that best embody the concepts.
For example, if the apodosis is "Canis familiaris" the synsetID would be 'dog.n.01'.
This is divinatory, so avoid literal interpretations if possible,
erring on the side of polysemy and applicability to a divinatory reading.
Provide a Python-formatted, single-quoted, comma-separated list of synsetIDs from Wordnet.
An example of response might be "['cat.n.01', 'dog.n.01', 'bird.n.01']".

CRITICAL: Return ONLY the raw Python list. Do NOT wrap it in markdown code blocks, backticks, or any other formatting.
Do NOT include ```python or ``` in your response.
Do NOT provide any explanation, preamble, or text other than the list itself.
Your response must start with [ and end with ].

Only provide noun synsetIDs that are from the WordNet lexical database.
If the synsetID you have found is for any other part of speech, omit it and find a related noun synset.
The prior text are instructions.
The apodosis I want you to evaluate follows.
"""


class AskClaude():
    def __init__(self, api_key=None, model="claude-sonnet-4-20250514"):
        """
        Initialize the Claude API client.
        
        Args:
            api_key: Anthropic API key. If None, will look for ANTHROPIC_API_KEY env variable
            model: Claude model to use (default: claude-sonnet-4-20250514)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        
        if self.api_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Anthropic client: {e}")
                self.client = None
        else:
            print("Warning: No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable.")
            self.client = None

    def no_gpt_error_message(self):
        """Returns a sentinel value to indicate Claude is unavailable"""
        return 'no_gpt_error_message'
    
    def _make_claude_request(self, prompt, max_tokens=1024):
        """
        Internal method to make API requests to Claude.
        
        Args:
            prompt: The prompt to send to Claude
            max_tokens: Maximum tokens in response
            
        Returns:
            Response text or error message
        """
        if self.client is None:
            return self.no_gpt_error_message()
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            print(f"Error making Claude API request: {e}")
            return self.no_gpt_error_message()

    def recommend_apodosis(self, text_to_examine):
        """
        Ask Claude to identify the apodosis in a divinatory text.
        
        Args:
            text_to_examine: The sentence to analyze
            
        Returns:
            Dictionary with 'full' and 'apodosis' keys, or error message
        """
        if self.client is None:
            return self.no_gpt_error_message()
                
        full_apodosis_prompt = recommend_apodosis_pre_prompt + text_to_examine

        parse_attempts = 3
        while parse_attempts > 0:
            parse_attempts -= 1
            claude_response = self._make_claude_request(full_apodosis_prompt)
            
            if claude_response == self.no_gpt_error_message():
                return self.no_gpt_error_message()
            
            # Strip markdown code blocks if present
            claude_response = claude_response.strip()
            if claude_response.startswith('```'):
                # Remove opening code block
                lines = claude_response.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                # Remove closing code block
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                claude_response = '\n'.join(lines).strip()
            
            try:
                response_json = json.loads(claude_response)
                return response_json
            except json.JSONDecodeError as e:
                print(f"Attempt to decode Claude's response as JSON failed. Trying {parse_attempts} more time(s).")
                print(f"Full response: {claude_response}")
                print(f"Error: {e}")
                if parse_attempts == 0:
                    print("Unable to get valid JSON from Claude after 3 attempts.")
                    return self.no_gpt_error_message()
        
    def modify_apodosis(self):
        """Placeholder for future functionality"""
        # maybe later
        pass
        
    def recommend_synsets(self, apodosis_to_examine):
        """
        Ask Claude to recommend WordNet synsets for an apodosis.
        
        Args:
            apodosis_to_examine: The apodosis text to analyze
            
        Returns:
            List of synset IDs or error message
        """
        if self.client is None:
            return self.no_gpt_error_message()
        
        full_synset_prompt = recommend_synsets_pre_prompt + apodosis_to_examine
        
        parse_attempts = 3
        while parse_attempts > 0:
            parse_attempts -= 1
            claude_response = self._make_claude_request(full_synset_prompt)
            
            if claude_response == self.no_gpt_error_message():
                return self.no_gpt_error_message()

            # Strip markdown code blocks if present
            claude_response = claude_response.strip()
            if claude_response.startswith('```'):
                # Remove opening code block
                lines = claude_response.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                # Remove closing code block
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                claude_response = '\n'.join(lines).strip()

            try:
                gpt_suggestions = ast.literal_eval(claude_response)
                return gpt_suggestions
            except (ValueError, SyntaxError) as e:
                print(f"Attempt to decode Claude's response with ast failed. Trying {parse_attempts} more time(s).")
                print(f"Full response: {claude_response}")
                print(f"Error: {e}")
                if parse_attempts == 0:
                    print("Unable to get valid list from Claude after 3 attempts.")
                    return self.no_gpt_error_message()
                    
    def modify_synsets(self):
        """Placeholder for future functionality"""
        # maybe later
        pass
