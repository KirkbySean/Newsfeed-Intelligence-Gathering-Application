from pydantic import BaseModel, Field
from ollama import chat
import sqlite3
from datetime import datetime
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from config import OLLAMA_MODEL, DATABASE_PATH
from pathlib import Path


class FinalReport(BaseModel):
    title: str
    executive_summary: str
    key_developments: list[str]
    detailed_assessment: str
    uncertainties: list[str]
    source_article_ids: list[int]

def get_report_input(article_id: int):
     with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        # Get current article, agent analysis and agent research
        # Get basic information about the article
        cursor.execute(
            """
            SELECT
                title,
                date
            FROM articles
            WHERE id = ?
            """,
            (article_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        title, date = row

        cursor.execute(
            """
            SELECT
                id,
                assessment_summary,
                confidence
            FROM assessments
            WHERE article_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (article_id,)
        )

        assessment = cursor.fetchone()

        if assessment is None:
            return None

        assessment_id, assessment_summary, confidence = assessment

        # Get developments belonging to this assessment
        cursor.execute(
            """
            SELECT development
            FROM assessment_developments
            WHERE assessment_id = ?
            """,
            (assessment_id,)
        )

        developments = [
            row[0] for row in cursor.fetchall()
        ]

        # Get uncertainties belonging to this assessment
        cursor.execute(
            """
            SELECT uncertainty
            FROM assessment_uncertainties
            WHERE assessment_id = ?
            """,
            (assessment_id,)
        )

        uncertainties = [
            row[0] for row in cursor.fetchall()
        ]

        return {
            "article_id": article_id,
            "title": title,
            "date": date,
            "assessment_summary": assessment_summary,
            "confidence": confidence,
            "developments": developments,
            "uncertainties": uncertainties,
        }


def get_report_inputs(start_date: str, end_date: str):

    # convert report boundaries into datetime objects
    start = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    ).replace(tzinfo=None)

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    ).replace(tzinfo=None)

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, date
            FROM articles
            WHERE assessed = ?
            """,
            (True,)
        )

        rows = cursor.fetchall()

    report_inputs = []

    for article_id, date_string in rows:

        # convert RSS date: into python time
        article_date = parsedate_to_datetime(
            date_string
        ).replace(tzinfo=None)

        # only include articles inside reporting period
        if start <= article_date < end:

            report_input = get_report_input(
                article_id
            )

            if report_input is not None:
                report_inputs.append(
                    report_input
                )

    return report_inputs


def generate_report(start_date: str, end_date: str):

    report_inputs = get_report_inputs(start_date, end_date)

    if not report_inputs:
        raise ValueError("No assessments available for report generation.")

    mission_obj = """
    You are a report generation and review agent.

    Your task is to produce a clear, concise report from a collection of
    previously completed article assessments.

    Each assessment may contain:
    - an article ID and title
    - key developments
    - an assessment summary
    - uncertainties
    - an assessment confidence value

    REPORTING RULES:
    - Use only information contained in the supplied assessments.
    - Do not introduce outside facts.
    - Combine developments that describe the same event or issue.
    - Do not present reported claims as independently verified facts.
    - Preserve important uncertainty and disagreement from the assessments.
    - Do not increase the certainty of a claim beyond what is supported by
      the supplied assessments.
    - Clearly distinguish reported developments from analytical conclusions.
    - Focus on the most important developments rather than repeating every
      detail from every assessment.
    - The detailed assessment should explain relationships between
      developments only when those relationships are supported by the
      supplied evidence.
    - source_article_ids must contain only article IDs present in the supplied
      assessments.
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
                Reporting period:
                {start_date} to {end_date}

                Generate a report from the following assessments:

                {report_inputs}
                """
            }
        ],
        format=FinalReport.model_json_schema()
    )

    report = FinalReport.model_validate_json(
        response.message.content
    )

    valid_article_ids = {
        item["article_id"]
        for item in report_inputs
    }

    for article_id in report.source_article_ids:
        if article_id not in valid_article_ids:
            raise ValueError(
                f"Report referenced article {article_id}, "
                "but that article was not supplied to Agent 4."
            )

    return report


def create_report_tables():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                executive_summary TEXT NOT NULL,
                detailed_assessment TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_developments (
                id INTEGER PRIMARY KEY,
                report_id INTEGER NOT NULL,
                development TEXT NOT NULL,

                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_uncertainties (
                id INTEGER PRIMARY KEY,
                report_id INTEGER NOT NULL,
                uncertainty TEXT NOT NULL,

                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_sources (
                id INTEGER PRIMARY KEY,
                report_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL,

                FOREIGN KEY (report_id) REFERENCES reports(id),
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """
        )

        connection.commit()


def save_report(report: FinalReport, start_date: str, end_date: str):

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO reports (
                title,
                executive_summary,
                detailed_assessment,
                period_start,
                period_end
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                report.title,
                report.executive_summary,
                report.detailed_assessment,
                start_date,
                end_date
            )
        )

        report_id = cursor.lastrowid

        for development in report.key_developments:
            cursor.execute(
                """
                INSERT INTO report_developments (
                    report_id,
                    development
                )
                VALUES (?, ?)
                """,
                (report_id, development)
            )

        for uncertainty in report.uncertainties:
            cursor.execute(
                """
                INSERT INTO report_uncertainties (
                    report_id,
                    uncertainty
                )
                VALUES (?, ?)
                """,
                (report_id, uncertainty)
            )

        for article_id in report.source_article_ids:
            cursor.execute(
                """
                INSERT INTO report_sources (
                    report_id,
                    article_id
                )
                VALUES (?, ?)
                """,
                (report_id, article_id)
            )

        connection.commit()

    return report_id


def add_report_period_columns():

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(reports)")
        columns = [row[1] for row in cursor.fetchall()]

        if "period_start" not in columns:
            cursor.execute(
                """
                ALTER TABLE reports
                ADD COLUMN period_start TEXT
                """
            )

            print("Added period_start column.")

        if "period_end" not in columns:
            cursor.execute(
                """
                ALTER TABLE reports
                ADD COLUMN period_end TEXT
                """
            )

            print("Added period_end column.")

        connection.commit()


def check_dates():
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, date
            FROM articles
            LIMIT 10
            """
        )

        for row in cursor.fetchall():
            print(row)


def create_report_text_file(
    report: FinalReport,
    report_id: int,
    start_date: str,
    end_date: str
):
    report_folder = Path("reports")
    report_folder.mkdir(exist_ok=True)

    filename = report_folder / f"report_{report_id}.txt"

    with open(filename, "w", encoding="utf-8") as file:

        file.write(f"{report.title}\n")
        file.write("=" * len(report.title) + "\n\n")

        file.write(
            f"Reporting Period: {start_date} to {end_date}\n"
        )
        file.write(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        file.write("EXECUTIVE SUMMARY\n")
        file.write("-----------------\n")
        file.write(report.executive_summary + "\n\n")

        file.write("KEY DEVELOPMENTS\n")
        file.write("----------------\n")

        for development in report.key_developments:
            file.write(f"- {development}\n")

        file.write("\n")

        file.write("DETAILED ASSESSMENT\n")
        file.write("-------------------\n")
        file.write(report.detailed_assessment + "\n\n")

        file.write("UNCERTAINTIES\n")
        file.write("-------------\n")

        for uncertainty in report.uncertainties:
            file.write(f"- {uncertainty}\n")

        file.write("\n")

        file.write("SOURCE ARTICLE IDS\n")
        file.write("------------------\n")

        for article_id in report.source_article_ids:
            file.write(f"- Article {article_id}\n")

    print(f"Created text report: {filename}")


def main():

    create_report_tables()
    add_report_period_columns()

    today = datetime.now()
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    report = generate_report(
        start_date,
        end_date
    )

    print(report)

    report_id = save_report(
        report,
        start_date,
        end_date
    )

    print(f"Saved report {report_id}")

    create_report_text_file(
        report,
        report_id,
        start_date,
        end_date
    )


if __name__ == "__main__":
    main()