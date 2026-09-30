from pydantic import BaseModel, Field
from ollama import chat
import sqlite3
from config import OLLAMA_MODEL, DATABASE_PATH


class Assessment(BaseModel):
    key_developments: list[str]
    assessment_summary: str
    uncertainties: list[str]
    confidence: float = Field(ge=0.0, le=1.0)

def get_assessment_input(article_id: int):

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        # Get current article, agent analysis and agent research
        cursor.execute(
            """
            SELECT
                a.title,
                a.summary,
                a.article,
                a.date,
                a.analysis_summary,
                a.reason,
                r.id,
                r.overall_summary
            FROM articles a
            JOIN research r ON r.article_id = a.id
            WHERE a.id = ?
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            (article_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        title, summary, article, date, analysis_summary, reason, research_id, overall_summary = row

        cursor.execute(
                    """
                    SELECT
                        a.id,
                        a.title,
                        a.date,
                        rs.summary
                    FROM research_sources rs
                    JOIN articles a
                        ON a.id = rs.related_article_id
                    WHERE rs.research_id = ?
                    """,
                    (research_id,)
                )

        sources = cursor.fetchall()

        return {
            "article_id": article_id,
            "title": title,
            "summary": summary,
            "article": article,
            "date": date,
            "analysis_summary": analysis_summary,
            "reason": reason,
            "research_summary": overall_summary,
            "sources": sources
        }


def create_assessment_tables():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY,
                article_id INTEGER NOT NULL,
                assessment_summary TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assessment_developments (
                id INTEGER PRIMARY KEY,
                assessment_id INTEGER NOT NULL,
                development TEXT NOT NULL,

                FOREIGN KEY (assessment_id) REFERENCES assessments(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assessment_uncertainties (
                id INTEGER PRIMARY KEY,
                assessment_id INTEGER NOT NULL,
                uncertainty TEXT NOT NULL,

                FOREIGN KEY (assessment_id) REFERENCES assessments(id)
            )
            """
        )

        connection.commit()


def save_assessment(article_id: int, assessment: Assessment):

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO assessments (
                article_id,
                assessment_summary,
                confidence
            )
            VALUES (?, ?, ?)
            """,
            (
                article_id,
                assessment.assessment_summary,
                assessment.confidence
            )
        )

        assessment_id = cursor.lastrowid

        for development in assessment.key_developments:
            cursor.execute(
                """
                INSERT INTO assessment_developments (
                    assessment_id,
                    development
                )
                VALUES (?, ?)
                """,
                (assessment_id, development)
            )

        for uncertainty in assessment.uncertainties:
            cursor.execute(
                """
                INSERT INTO assessment_uncertainties (
                    assessment_id,
                    uncertainty
                )
                VALUES (?, ?)
                """,
                (assessment_id, uncertainty)
            )

        # Only mark assessed after everything was stored successfully
        cursor.execute(
            """
            UPDATE articles
            SET assessed = ?
            WHERE id = ?
            """,
            (True, article_id)
        )

        connection.commit()


def assess_article(article_id: int):

    evidence = get_assessment_input(article_id)

    if evidence is None:
        raise ValueError(
            f"No research available for article {article_id}"
        )

    mission_obj = """
    You are an assessment agent.

    Analyze the supplied current article, initial analysis, and historical
    research.

    Determine what important developments are introduced by the current
    article and how they relate to the previous reporting provided.

    EVIDENCE RULES:
    - Use only information contained in the supplied evidence.
    - Distinguish reported claims from independently established facts.
    - Do not treat a claim as verified merely because a news article reports it.
    - Attribute claims to the relevant source or actor when appropriate.
    - "New" means new relative to the supplied database evidence, not
    necessarily new in the real world.
    - Do not infer motives, capabilities, intentions, or causation unless
    supported by the supplied evidence.
    - Clearly identify contradictions, missing information, and uncertainties.
    - It is acceptable to conclude that the evidence does not support a
    stronger assessment.

    Confidence represents confidence in the assessment based on the quality,
    consistency, and completeness of the supplied evidence, from 0.0 to 1.0.
    """

    response = chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": mission_obj
            },
            {
                "role": "user",
                "content": f"""
                Assess the following evidence packet.

                The 'article' field contains the current article.
                'analysis_summary' and 'reason' contain the initial analyst's findings.
                'research_summary' contains the research agent's overall findings.
                'sources' contains previous articles retrieved by the research agent.

                EVIDENCE:
                {evidence}
                """
            }
        ],
        format=Assessment.model_json_schema()
    )

    assessment = Assessment.model_validate_json(
        response.message.content
    )

    return assessment


def assessment_select():

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM articles
            WHERE relevant = ?
              AND researched = ?
              AND assessed = ?
            """,
            (True, True, False)
        )

        rows = cursor.fetchall()

    print(f"Articles waiting for assessment: {len(rows)}")

    for row in rows:
        article_id = row[0]

        try:
            assessment = assess_article(article_id)

            print(assessment)

            save_assessment(article_id, assessment)

            print(f"Saved assessment for article {article_id}")

        except Exception as e:
            print(f"Failed to assess article {article_id}")
            print(e)


def main():
    create_assessment_tables()
    assessment_select()


if __name__ == "__main__":
    main()