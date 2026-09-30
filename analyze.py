from ollama import chat
from typing import Literal
import sqlite3
from pydantic import BaseModel, Field
from config import OLLAMA_MODEL, DATABASE_PATH

class ArticleAnalysis(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0)
    category: Literal[
        "POLITICAL",
        "ECONOMIC",
        "SECURITY",
        "DIPLOMATIC",
        "TECHNOLOGY",
        "OTHER",
        "NOT_RELEVANT"
    ]
    analysis_summary: str
    reason: str


def analyze_articles():
    #Adjust to fit your mission objective
    mission_obj = """
    You are a strategic Analyst,

    Your purpose is to determine the best places in Europe to place NATO military strategic assets. 
    When analyzing an article:
        - Distinguish in between facts and propaganda/opinion
        - Assess how relevant an article is to your purpose, give it a score from 0 to 1
        - Categorize the article only if it is relevant
        - make sure it's relevance is well argued
    """
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT title, summary, link, date, article FROM articles WHERE analyzed = ?", (False,))
        rows = cursor.fetchall()

        for title, summary, link, date, article in rows:
            try:
                article_input = f"""
                                    TITLE:
                                    {title}

                                    PUBLISHED:
                                    {date}

                                    RSS SUMMARY:
                                    {summary}

                                    ARTICLE:
                                    {article}
                                """
                
                response = chat(
                    model = OLLAMA_MODEL,
                    messages = [
                        {
                            "role": "system",
                            "content": mission_obj
                        },
                        {
                            "role": "user",
                            "content": article_input
                        }
                    ],

                    format = ArticleAnalysis.model_json_schema()
                )
                #print(response.message.content)

                analysis = ArticleAnalysis.model_validate_json(
                    response.message.content
                )
                cursor.execute(
                    """
                    UPDATE articles
                    SET analyzed = ?,
                        relevant = ?,
                        relevance = ?,
                        category = ?,
                        analysis_summary = ?,
                        reason = ?
                    WHERE link = ?
                    """,
                    (True,
                    analysis.relevance >= 0.5, #subject to change
                    analysis.relevance,
                    analysis.category,
                    analysis.analysis_summary,
                    analysis.reason,
                    link)
                )
                print(f"Article updated {link}")
                connection.commit()
            except Exception as e:
                print(f"Failed to analyze {link}")
                print(e)
        

def main():
    analyze_articles()


if __name__ == "__main__":
    main()    