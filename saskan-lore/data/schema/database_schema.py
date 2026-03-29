documents = [
    "id",
    "title",
    "source_text",
    "created_at",
file_path
content_hash
]

chunks = [
    id
    document_id
    text
    chunk_index
    char_start
char_end
]

entities = [
id
name
type   -- (character, place, faction, etc.)
]

entity_aliases = [
    id
entity_id
alias
]

claims = [
    id
document_id
chunk_id
statement
source_span
confidence
claim_type
asserted_by_entity_id nullable
applies_to_entity_id nullable
era_label nullable
needs_review = true
]

claim_entities = [
    claim_id
entity_id
role   -- optional later
]

documents = [
    id
file_path
source_text   -- full text
]

eval_questions = [
    id
question
expected_answer
]

eval_results = [
    id
question_id
model_answer
passed
notes
]

relationships
-------------
id
source_type      -- 'entity', 'claim', 'document', 'chunk'
source_id
relationship_type
target_type      -- 'entity', 'claim', 'document', 'chunk'
target_id
evidence_chunk_id   -- nullable
notes              -- nullable

