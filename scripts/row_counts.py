"""Print active row counts for all application tables."""

from saskan_lore.infra.db import dba

counts = dba.row_counts()
width = max(len(k) for k in counts)
for table, count in counts.items():
    print(f"  {table:<{width}}  {count}")
