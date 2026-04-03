# R5 Retrieval and Answering — Test Cases

Test case register for `tests/unit/r5_retrieval/test_r5_retrieval.py`.

---

## retrieval.py

| ID | Function | Description | Expected |
| --- | --- | --- | --- |
| TC-R5-01 | `tokenize` | Splits on whitespace and punctuation; lowercases | `["oath", "breaking", "covenant"]` from `"Oath-breaking, Covenant?"` |
| TC-R5-02 | `tokenize` | Empty string and punctuation-only input | Returns `[]` in both cases; no error |
| TC-R5-03 | `retrieve` | Query matching an approved claim | Returns one `RetrievalHit` with correct text, truth_status, document_title, chunk_sequence |
| TC-R5-04 | `retrieve` | Query matching only a rejected claim | Returns `[]`; rejected claims are excluded |
| TC-R5-05 | `retrieve` | Query that tokenizes to nothing (e.g. `"???"`) | Returns `[]`; no DB call attempted |
| TC-R5-06 | `retrieve` | Valid tokens that match no approved claims | Returns `[]`; no error |
| TC-R5-07 | `retrieve` | `top_n=1` with two matching approved claims | Returns exactly one result |
| TC-R5-08 | `format_context` | Formats hits into numbered context block | Output contains `[1]`, truth status, document title, `chunk N`, source span, claim text |
| TC-R5-12 | `format_context` | Empty hits list | Returns `""` |
| TC-R5-13 | `format_context` | Multiple hits | Output contains `[1]` and `[2]`; entries separated by blank line |
| TC-R5-14 | `retrieve` | Approved claim with `is_active=False` | Excluded from results |

---

## answering.py

| ID | Function | Description | Expected |
| --- | --- | --- | --- |
| TC-R5-09 | `answer` | No retrieval hits — model must not be called | `answerable=False`, `answer=None`, `evidence=[]`, `complete()` not called |
| TC-R5-10 | `answer` | Hits present — model called, evidence matches | `answerable=True`, `answer` equals model response, `evidence` matches retrieved claim IDs |
| TC-R5-11 | `answer` | Model returns cannot-answer signal | `answerable=True`, `answer` contains the cannot-answer string, `evidence` non-empty |
