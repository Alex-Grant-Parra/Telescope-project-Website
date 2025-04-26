from sqlalchemy import create_engine, MetaData, Table, select, update, text
from sqlalchemy.orm import Session

# Connect to the database with AUTOCOMMIT
engine = create_engine('sqlite:///Data.db', isolation_level="AUTOCOMMIT")
metadata = MetaData()

# Reflect the table
hd_star_table = Table('HDSTARtable', metadata, autoload_with=engine)

with Session(engine) as session:
    session.execute(text("BEGIN IMMEDIATE TRANSACTION;"))  # <-- wrapped in text()

    results = session.execute(select(hd_star_table.c.Name)).scalars().all()
    print(f"Fetched {len(results)} records. Starting updates...")

    update_count = 0

    for original_name in results:
        if not str(original_name).startswith("HD"):
            new_name = f"HD{original_name}"
            session.execute(
                update(hd_star_table)
                .where(hd_star_table.c.Name == original_name)
                .values(Name=new_name)
            )
            print(f"Updating '{original_name}' to '{new_name}'...")
            update_count += 1

    session.commit()

print(f"Finished updating! Total records updated: {update_count}")
