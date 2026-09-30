import feedparser
import sqlite3
import requests
from bs4 import BeautifulSoup
from config import DATABASE_PATH

def parse_rss(rss_link):
    feed = feedparser.parse(rss_link)

    source = feed.feed.get("title", "Unknown Source")

    print(f"RSS Feed: {source}")

    for entry in feed.entries:
        create_article_sql(entry, source)


def create_article_sql(entry, source):

    title = entry.get("title", "")
    summary = entry.get("summary", "")
    date = entry.get("published", "")
    link = entry.get("link", "")

    # Title and link are required
    if not title or not link:
        print("SKIP: RSS entry missing title or link")
        return

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        # Check whether article already exists
        cursor.execute(
            """
            SELECT id
            FROM articles
            WHERE link = ?
            """,
            (link,)
        )

        result = cursor.fetchone()

        if result is not None:
            print(f"SKIP: {title}")
            return

        print(f"NEW ARTICLE: {title}")

        article = get_article(link)

        if article is None:
            print(
                f"SKIP: Could not extract article text for '{title}'"
            )
            return

        cursor.execute(
            """
            INSERT INTO articles (
                title,
                summary,
                source,
                date,
                link,
                article,
                analyzed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                summary,
                source,
                date,
                link,
                article,
                False
            )
        )

        connection.commit()


def create_tables():
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                summary TEXT,
                source TEXT,
                date TEXT,
                link TEXT UNIQUE,
                article TEXT,
                analyzed BOOLEAN DEFAULT FALSE,
                relevant BOOLEAN,
                relevance FLOAT,
                category TEXT,
                analysis_summary TEXT,
                reason TEXT,
                researched BOOLEAN DEFAULT FALSE
            )
            """
        )

        connection.commit()


def print_table():
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM articles WHERE analyzed = ?", (False,))
        for row in cursor:
            print(row)


def get_article(link):
    try:
        response = requests.get(
            link,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        article = soup.find("article")

        if article is None:
            print(f"WARNING: Could not extract article from: {link}")
            return None

        # Remove figures
        for figure in article.find_all("figure"):
            figure.decompose()

        paragraphs = article.find_all("p")

        article_text = "\n".join(
            paragraph.get_text(strip=True)
            for paragraph in paragraphs
        )

        if not article_text:
            print(f"WARNING: No article text found: {link}")
            return None

        return article_text

    except requests.RequestException as e:
        print(f"WARNING: Failed to download {link}")
        print(f"Reason: {e}")
        return None


def main():

    create_tables()

    parse_rss(
        "https://feeds.bbci.co.uk/news/rss.xml"
    )


if __name__ == "__main__":
    main()  