"""Print the latest eval result per question, alongside its expected answer, for grading.

Older results from previous `evaluate()` runs are preserved in the DB but
not shown here — only the most recent result per question is displayed.
"""

from sqlalchemy import func

from saskan_lore.infra.db.db import get_session
from saskan_lore.data.models import EvalQuestion, EvalResult

with get_session() as session:
    latest_ids = session.query(func.max(EvalResult.id)).group_by(EvalResult.question_id)
    rows = (
        session.query(EvalResult, EvalQuestion)
        .join(EvalQuestion, EvalResult.question_id == EvalQuestion.id)
        .filter(EvalResult.id.in_(latest_ids))
        .order_by(EvalQuestion.question_id)
        .all()
    )
    for result, question in rows:
        print("=" * 70)
        print(f"result_id={result.id}  {question.question_id}  {question.question_text}")
        print(f"  expected : {question.expected_answer}")
        print(f"  evidence : {result.retrieved_evidence}")
        print(f"  answer   : {result.model_answer}")
        graded = f"{result.pass_fail or '(ungraded)'}"
        if result.failure_type:
            graded += f" / {result.failure_type}"
        print(f"  graded   : {graded}")
        print()
