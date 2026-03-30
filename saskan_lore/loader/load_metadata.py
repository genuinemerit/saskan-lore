import sqlite3
# import json

conn = sqlite3.connect("lore.db")


def insert_doc(doc):
    conn.execute("""
    INSERT INTO documents (doc_id, title, region, era, text)
    VALUES (?, ?, ?, ?, ?)
    """, (
        doc["doc_id"],
        doc["title"],
        doc.get("region"),
        doc.get("era"),
        doc["text"]
    ))
