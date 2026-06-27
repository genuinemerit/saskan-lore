"""Print a summary of the database schema and row counts."""

from saskan_lore.infra.db import dba

dba.summary()
