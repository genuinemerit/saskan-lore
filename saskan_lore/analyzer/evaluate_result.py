import sqlite3

# import json

conn = sqlite3.connect("lore.db")


def record_result(q, expected, actual, passed, notes=""):
    conn.execute(
        """
        INSERT INTO eval_results
        (question, expected, actual, passed, notes)
        VALUES (?, ?, ?, ?, ?)
    """,
        (q, expected, actual, passed, notes),
    )
