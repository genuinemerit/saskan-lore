from collections import Counter

character_counts = Counter()


for chunk in chunks:
    for name in character_list:
        if name in chunk:
            character_counts[name] += 1