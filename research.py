from ollama import chat
from typing import Literal
import sqlite3
from pydantic import BaseModel, Field
from config import OLLAMA_MODEL, DATABASE_PATH

class RelatedArticle(BaseModel):
    article_id: int
    summary: str


class ResearchAnalysis(BaseModel):
    overall_summary: str
    related_articles: list[RelatedArticle]


def create_research_tables():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY,
                article_id INTEGER NOT NULL,
                overall_summary TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS research_sources (
                id INTEGER PRIMARY KEY,
                research_id INTEGER NOT NULL,
                related_article_id INTEGER NOT NULL,
                summary TEXT NOT NULL,

                FOREIGN KEY (research_id) REFERENCES research(id),
                FOREIGN KEY (related_article_id) REFERENCES articles(id)
            )
            """
        )

        connection.commit()


def save_research(article_id: int, research: ResearchAnalysis):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        # Save the overall research result
        cursor.execute(
            """
            INSERT INTO research (article_id, overall_summary)
            VALUES (?, ?)
            """,
            (
                article_id,
                research.overall_summary
            )
        )

        research_id = cursor.lastrowid

        # Save every related article
        for related_article in research.related_articles:
            cursor.execute(
                """
                INSERT INTO research_sources (
                    research_id,
                    related_article_id,
                    summary
                )
                VALUES (?, ?, ?)
                """,
                (
                    research_id,
                    related_article.article_id,
                    related_article.summary
                )
            )

        # Only mark the article researched after everything
        # above succeeded.
        cursor.execute(
            """
            UPDATE articles
            SET researched = ?
            WHERE id = ?
            """,
            (True, article_id)
        )

        connection.commit()


def search_articles(search_term: str, exclude_id: int):
    words = search_term.split()

    conditions = " OR ".join(
        ["article LIKE ?" for _ in words]
    )

    parameters = [f"%{word}%" for word in words]

    # relevant = True, then exclude current article
    parameters.extend([True, exclude_id])

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT id, title, summary, link, date
            FROM articles
            WHERE ({conditions})
              AND relevant = ?
              AND id != ?
            ORDER BY relevance DESC
            LIMIT 10
            """,
            parameters
        )

        rows = cursor.fetchall()

    return rows


def agent_search_articles(rows):
    mission_obj = """
    You're a news research assistant.

    RESEARCH PHASE:
    Use search_database to investigate whether the article database contains
    previous reporting relevant to the current article.

    You MUST perform at least one database search before finishing your research.
    You may perform multiple searches using different terms when useful.

    When you believe you have enough information, stop calling tools and state
    that your research is complete.

    IMPORTANT:
    - Only treat articles returned by search_database as previous reporting.
    - Never invent articles or article IDs.
    - It is acceptable for database searches to find no relevant articles.
    """
    
    
    for article_id, title, summary, link, date, analysis_summary, reason in rows:
        try:

            retrieved_ids = set()
            tool_was_used = False
            
            def search_database(search_term: str): #wrapper to stop agent from using it's own article
                results = search_articles(search_term, article_id)

                for result in results:
                    retrieved_ids.add(result[0])  # result[0] is article id

                return results
            
            article_input = f"""
                                TITLE:
                                {title}

                                PUBLISHED:
                                {date}

                                LINK:
                                {link}

                                RSS SUMMARY:
                                {summary}

                                ANALYSIS SUMMARY:
                                {analysis_summary}

                                ANALYSIS REASONING:
                                {reason}
                            """

            messages = [
                {
                    "role": "system",
                    "content": mission_obj
                },
                {
                    "role": "user",
                    "content": article_input
                }
            ]
            max_i = 10
            for i in range(max_i): #loop for agent to keep recalling the tool
                response = chat(
                    model = OLLAMA_MODEL,
                    messages = messages,
                    tools = [search_database],
                    #format = ResearchAnalysis.model_json_schema()
                )
                
                messages.append(response.message)

                if response.message.tool_calls: #if agent asks to use a tool
                    for tool_call in response.message.tool_calls: #for every tool call get the agents arguments and use the function to produce the results
                        print(tool_call.function.name)
                        print(tool_call.function.arguments)
                        if tool_call.function.name == "search_database":
                            tool_was_used = True
                            search_term = tool_call.function.arguments["search_term"]
                            results = search_database(search_term)

                            print(f"\nSEARCH TERM: {search_term}")
                            print(f"FOUND {len(results)} RESULTS:")

                            for result in results:
                                print(result)

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_name": tool_call.function.name,
                                    "content": str(results)
                                }
                            )

                else:
                    # Don't allow the agent to finish without searching
                    if not tool_was_used:
                        raise ValueError(
                            "Research agent produced an answer without searching the database."
                        )

                    # Ask for the final structured result
                    messages.append(
                        {
                            "role": "user",
                            "content": """
                            Research is complete.

                            Now return your final research analysis.
                            Only include related articles that were actually returned by
                            search_database. Use their exact article_id values.
                            """
                        }
                    )

                    final_response = chat(
                        model=OLLAMA_MODEL,
                        messages=messages,
                        format=ResearchAnalysis.model_json_schema()
                    )

                    research = ResearchAnalysis.model_validate_json(
                        final_response.message.content
                    )

                    break
            else:
                raise RuntimeError("Research agent exceeded maximum iterations")

            #print(research)
            #verify that agent actually retrieved the correct id and didn't hallucinate and that it actually used the tool provided
            if not tool_was_used:
                raise ValueError(
                    "Research agent produced an answer without searching the database."
                )

            for related_article in research.related_articles:
                if related_article.article_id not in retrieved_ids:
                    raise ValueError(
                        f"Agent returned article {related_article.article_id}, "
                        "but that article was never retrieved by the search tool."
                    )
            save_research(article_id, research)
            print(f"Saved research for article {article_id}")
            #break #DELETE AFTER TESTING

        except Exception as e:
            print(f"Failed to perform research {link}")
            print(e)


def researchSelect():
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("""
        SELECT id, title, summary, link, date, analysis_summary, reason
        FROM articles 
        WHERE relevant = ?
            AND researched = ?
        """,
        (True, False)
    )
    rows = cursor.fetchall()
    print(f"Articles waiting for research: {len(rows)}")

    agent_search_articles(rows)
        

def researchReset(): #FOR TESTING ONLY RESETS ALL RESEARCH TO FALSE
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        # Delete child rows first
        cursor.execute("DELETE FROM research_sources")
        cursor.execute("DELETE FROM research")

        # Reset pipeline state
        cursor.execute(
            """
            UPDATE articles
            SET researched = ?
            """,
            (False,)
        )

        connection.commit()

        print("Research data cleared and all articles reset.")

def main():
    #researchReset()
    create_research_tables()
    researchSelect()


if __name__ == "__main__":
    main() 