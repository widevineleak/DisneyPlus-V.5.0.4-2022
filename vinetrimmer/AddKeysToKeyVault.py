import argparse
import re
import sqlite3

def main():
    parser = argparse.ArgumentParser(
        description="Simple script to add or update key information to a SQLite key vault db"
    )
    parser.add_argument(
        "-t", "--table",
        help="Table to store keys in (e.g., amazon, netflix, disneyplus)",
        required=True
    )
    parser.add_argument(
        "-i", "--input",
        help="Data file containing KID:KEY pairs, optionally followed by :<title here>",
        required=True
    )
    parser.add_argument(
        "-d", "--dry-run",
        help="Execute the script, but do not save/commit changes",
        action="store_true",
        required=False
    )
    parser.add_argument(
        "-o", "--output",
        help="SQLite database file",
        required=True
    )
    args = parser.parse_args()

    try:
        connection = sqlite3.connect(args.output)
        cursor = connection.cursor()

        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{args.table}` (kid TEXT NOT NULL, key_ TEXT NOT NULL, title TEXT)")

        add_count = 0
        update_count = 0
        existed_count = 0

        with open(args.input, encoding="utf-8") as fd:
            input_data = fd.read()

        for line in input_data.splitlines():
            match = re.search(r"^(?P<kid>[0-9a-fA-F]{32}):(?P<key>[0-9a-fA-F]{32})(:(?P<title>[\w .:-]*))?$", line)
            if not match:
                continue
            kid = match.group("kid").lower()
            key = match.group("key").lower()
            title = match.group("title") or None

            cursor.execute(
                f"SELECT title FROM `{args.table}` WHERE `kid`=:kid",
                {"kid": kid}
            )
            exists = cursor.fetchone()

            if exists:
                if title and not exists[0]:
                    update_count += 1
                    print(f"Updating {args.table} {kid}: {title}")
                    cursor.execute(
                        f"UPDATE `{args.table}` SET `title`=:title WHERE `kid`=:kid",
                        {"title": title, "kid": kid}
                    )
                else:
                    existed_count += 1
                    print(f"Key {args.table} {kid} already exists in the db with no differences, skipping...")
            else:
                add_count += 1
                print(f"Adding {args.table} {kid} ({title}): {key}")
                cursor.execute(
                    f"INSERT INTO `{args.table}` (kid, key_, title) VALUES (:kid, :key, :title)",
                    {"kid": kid, "key": key, "title": title}
                )

        if args.dry_run:
            print("--dry run enabled, have not committed any changes.")
        else:
            connection.commit()

        print(
            "Done!\n"
            f"{add_count} added, {update_count} updated in some way, {existed_count} already existed (skipped)"
        )

    except sqlite3.Error as err:
        print(f"SQLite Error: {err}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    main()
