import sqlite3


def add_assessed_column():
    with sqlite3.connect("articles.db") as connection:
        cursor = connection.cursor()

        # Get the existing columns in articles
        cursor.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]

        if "assessed" not in columns:
            cursor.execute(
                """
                ALTER TABLE articles
                ADD COLUMN assessed BOOLEAN DEFAULT FALSE
                """
            )
            print("Added 'assessed' column to articles.")
        else:
            print("'assessed' column already exists.")

        connection.commit()


def main():
    add_assessed_column()


if __name__ == "__main__":
    main()