def slice_substring_per_content(main_string, slice_command):
    # slice a string per content rather than indices
    # returns index where it starts and the substring indicated by the slice_command
    # if there is an error, the index will be -1 and the substring will be that error

    if slice_command == '':
        return -1, "Please include some term to search for in slice notation, e.g. 'hello:world' "
    
    if (":" not in slice_command): # Though not the intended use, should reply when looking for "h" in "hello", I guess.
        if (slice_command in main_string):
            starts_at = main_string.find(slice_command)
            return starts_at, slice_command
        else:
            return -1, "The search term is not found in the string"
        
    parts_list = slice_command.split(":")
    
    if len(parts_list) > 2: # if there are multiple colons (error)
        return -1, "Please include only one colon, no stride per https://python-reference.readthedocs.io/en/latest/docs/brackets/slicing.html"

    elif (parts_list[0] == '') and (parts_list[1] == ''):
        return -1, "Please include a term to the right and/or left of the colon per https://python-reference.readthedocs.io/en/latest/docs/brackets/slicing.html"

    else:
        if parts_list[0] == '': # EVERYTHING UP TO AND INCLUDING TERM, e.g. ":butts"
            part2_index_list = find_all_match_indices(main_string, parts_list[1])
            if len(part2_index_list) == 1:
                ends_at = part2_index_list[0] + len(parts_list[1]) # the easy case, where it only has one match
                return 0, main_string[0:ends_at]
            else: # multiple matches
                # disambiguate and present options for selection
                substrings = []
                for x in range(len(part2_index_list)):
                    ends_at = part2_index_list[x] +len(parts_list[1])
                    this_option = main_string[0:ends_at]
                    substrings.append(this_option)
                intended_substring_index = prompt_to_disambiguate_substrings(substrings)
                return 0, substrings[intended_substring_index]
        
            
        elif parts_list[1] == '': # EVERYTHING INCLUDING AND AFTER TERM, e.g. "big:"
            part1_index_list = find_all_match_indices(main_string, parts_list[0])
            if len(part1_index_list) == 1:
                starts_at = part1_index_list[0]
                ends_at = len(main_string)
                return starts_at, main_string[starts_at:ends_at]
            else:
                #disambiguate and present options for selection
                substrings = []
                for x in range(len(part1_index_list)):
                    starts_at = part1_index_list[x]
                    ends_at = len(main_string)
                    this_option = main_string[starts_at:ends_at]
                    substrings.append(this_option)
                intended_substring_index = prompt_to_disambiguate_substrings(substrings)
                return 0, substrings[intended_substring_index]

            
        else: # EVERYTHING INCLUDING AND BETWEEN TERMS, e.g. "big:butts"
            part1_index_list = find_all_match_indices(main_string, parts_list[0])
            part2_index_list = find_all_match_indices(main_string, parts_list[1])

            if (len(part1_index_list) == 1) and (len(part2_index_list) == 1):
                starts_at = part1_index_list[0]
                ends_at   = part2_index_list[0] +len(parts_list[1])
                substring = main_string[starts_at:ends_at]
                return starts_at, substring
            else:
                # THERE MIGHT BE MULTIPLE MATCHES, NEED TO DISAMBIGUATE
                #disambiguate and present options for selection
                permutations = [[x, y] for x in part1_index_list for y in part2_index_list  if x<y]
                substrings = []
                for permutation in permutations:
                    starts_at = permutation[0]
                    ends_at   = permutation[1] +len(parts_list[1])
                    this_possibility = main_string[starts_at:ends_at]
                    substrings.append(this_possibility)
                intended_substring_index = prompt_to_disambiguate_substrings(substrings)
                return 0, substrings[intended_substring_index]
