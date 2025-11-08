#!/usr/bin/env python3
"""
Apodosis Reviewer - A tool for reviewing apodosis tags with WordNet synsets
"""

import re
import os
from datetime import datetime
from tkinter import Tk, filedialog


def select_file():
    """Open a file dialog to select a text file"""
    root = Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front
    
    file_path = filedialog.askopenfilename(
        title="Select a text file to process",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    
    root.destroy()
    return file_path


def generate_output_filename(input_path):
    """Generate output filename with date/time suffix"""
    directory = os.path.dirname(input_path)
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{name}_{timestamp}{ext}"
    
    return os.path.join(directory, output_filename)


def parse_apodosis_tags(text):
    """Parse the text to find all paragraphs containing apodosis tags"""
    # Pattern to match apodosis tags with wn_only attribute
    apodosis_pattern = r'<apodosis\s+wn_only="([^"]+)">([^<]+)</apodosis>'
    
    apodoses = []
    lines = text.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        matches = re.finditer(apodosis_pattern, line)
        for match in matches:
            synsets_str = match.group(1)
            apodosis_text = match.group(2)
            
            # Parse synset IDs
            synset_ids = [s.strip() for s in synsets_str.split(',')]
            
            apodoses.append({
                'line_num': line_num,
                'paragraph': line,
                'apodosis_text': apodosis_text,
                'synset_ids': synset_ids,
                'full_match': match.group(0)
            })
    
    return apodoses


def get_wordnet_info(synset_id):
    """
    Get WordNet information for a synset ID
    Returns: (synset_id, lemma, gloss)
    """
    try:
        from nltk.corpus import wordnet as wn
        
        # Parse the synset ID (e.g., "word.pos.nn")
        synset = wn.synset(synset_id)
        lemma = synset.lemmas()[0].name()  # Get first lemma
        gloss = synset.definition()
        
        return (synset_id, lemma, gloss)
    except Exception as e:
        return (synset_id, "ERROR", f"Could not retrieve: {str(e)}")


def ensure_nltk_data():
    """Ensure NLTK WordNet data is available"""
    try:
        import nltk
        from nltk.corpus import wordnet as wn
        # Test if wordnet is available
        wn.synsets('test')
    except LookupError:
        print("Downloading WordNet data...")
        import nltk
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
    except ImportError:
        print("\nWARNING: NLTK not installed. WordNet lookups will fail.")
        print("Install with: pip install nltk")
        input("Press Enter to continue anyway...")


def bold_text(text, to_bold):
    """Return text with the specified portion in bold using ANSI codes"""
    # ANSI escape codes for bold
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    return text.replace(to_bold, f"{BOLD}{to_bold}{RESET}")


def display_apodosis(apodosis_data, index, total):
    """Display an apodosis with its WordNet information"""
    print("\n" + "="*80)
    print(f"Apodosis {index + 1} of {total} ({(index + 1) / total * 100:.1f}% complete)")
    print("="*80)
    
    # Display paragraph with bolded apodosis
    paragraph = apodosis_data['paragraph']
    apodosis_text = apodosis_data['apodosis_text']
    bolded_paragraph = bold_text(paragraph, apodosis_data['full_match'])
    print(f"\nLine {apodosis_data['line_num']}:")
    print(bolded_paragraph)
    
    # Display WordNet synsets
    print(f"\nWordNet Synsets for: {apodosis_text}")
    print("-" * 80)
    for synset_id in apodosis_data['synset_ids']:
        synset_id_clean = synset_id.strip()
        synset_info = get_wordnet_info(synset_id_clean)
        print(f"  ID: {synset_info[0]}")
        print(f"  Lemma: {synset_info[1]}")
        print(f"  Gloss: {synset_info[2]}")
        print()


def process_apodoses(input_file):
    """Main processing function"""
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Parse apodoses
    apodoses = parse_apodosis_tags(text)
    
    if not apodoses:
        print("No apodosis tags found in the file.")
        return
    
    print(f"\nFound {len(apodoses)} apodosis tags to review.")
    
    # Generate output file
    output_file = generate_output_filename(input_file)
    print(f"Output will be saved to: {output_file}")
    
    # Create/open output file
    responses = []
    current_index = 0
    
    while current_index < len(apodoses):
        apodosis = apodoses[current_index]
        
        # Display current apodosis
        display_apodosis(apodosis, current_index, len(apodoses))
        
        # Get user input
        valid_chars = set('gixmfrn')
        additional_message = ""
        
        while True:
            print("\nOptions:")
            print("  g = looks good")
            print("  i = incomplete synsets")
            print("  x = excess synsets")
            print("  m = more words needed in phrase")
            print("  f = fewer words needed")
            print("  r = redo my last answer")
            print("  n = STOP processing")
            if additional_message:
                print(f"\n{additional_message}")
            
            user_input = input("\nYour response: ").strip().lower()
            
            # Parse input: extract all alphabetic characters
            all_chars = [c for c in user_input if c.isalpha()]
            
            # Separate valid and invalid characters
            valid_inputs = [c for c in all_chars if c in valid_chars]
            invalid_chars = [c for c in all_chars if c not in valid_chars]
            
            # Check if 'n' appears with other letters
            if 'n' in valid_inputs and len(valid_inputs) > 1:
                additional_message = "n must be submitted alone"
                continue
            
            # Handle the different cases
            if not valid_inputs:
                additional_message = "No valid input detected. Please use one of the listed options."
                continue
            
            # Reset additional message for next iteration
            additional_message = ""
            
            # Check for 'n' (stop processing)
            if valid_inputs == ['n']:
                print("\nStopping processing...")
                return  # Exit the main processing loop entirely
            
            # Check for 'r' (redo)
            if 'r' in valid_inputs:
                if current_index > 0:
                    current_index -= 1
                    # Remove last response
                    if responses:
                        responses.pop()
                    print("\nGoing back to previous apodosis...")
                    break  # Break inner loop to show previous apodosis
                else:
                    print("\nCannot go back - this is the first apodosis.")
                    continue
            
            # Valid input - log it
            response_str = ','.join(valid_inputs)
            responses.append({
                'line_num': apodosis['line_num'],
                'response': response_str,
                'apodosis_text': apodosis['apodosis_text'],
                'invalid_chars': invalid_chars
            })
            
            current_index += 1
            break  # Break inner loop to move to next apodosis
    
    # Write output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Apodosis Review Session\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input file: {input_file}\n")
        f.write(f"Total apodoses: {len(apodoses)}\n")
        f.write(f"Reviewed: {len(responses)}\n")
        f.write("\n" + "="*80 + "\n\n")
        
        for response in responses:
            f.write(f"Line {response['line_num']}: {response['response']}")
            if response['invalid_chars']:
                invalid_str = ','.join(response['invalid_chars'])
                f.write(f" [Invalid chars: {invalid_str}]")
            f.write("\n")
            #f.write(f"  Apodosis: {response['apodosis_text']}\n\n")
    
    # Final message
    if current_index >= len(apodoses):
        print("\n" + "="*80)
        print("All apodoses have been reviewed!")
        print("="*80)
    
    print(f"\nReview complete. Results saved to: {output_file}")
    print(f"Reviewed {len(responses)} of {len(apodoses)} apodoses.")


def main():
    """Main entry point"""
    print("Apodosis Reviewer")
    print("="*80)
    
    # Ensure NLTK data is available
    ensure_nltk_data()
    
    # Select file
    input_file = select_file()
    
    if not input_file:
        print("No file selected. Exiting.")
        return
    
    print(f"\nSelected file: {input_file}")
    
    # Process the file
    process_apodoses(input_file)


if __name__ == "__main__":
    main()
