"""One-off: remove AI history threads that were left empty by the trace-write bug.

Those threads list under their question and open as "This conversation is empty",
because `_save_turn` wrote the tool trace before the messages and an un-storable
trace aborted the turn (see tests/test_ai_history_persistence.py). The code no
longer produces them; this clears the ones already saved.

Dry run by default:
    python scripts_purge_empty.py            # count them
    python scripts_purge_empty.py --delete   # remove them
"""
import asyncio
import sys

from database import connect_to_mongo, close_mongo_connection, get_database


async def main(delete: bool) -> None:
    await connect_to_mongo()
    db = get_database()
    empty = {"$or": [{"messages": {"$size": 0}}, {"messages": {"$exists": False}}]}
    docs = [d async for d in db["ai_conversations"].find(empty,
                                                         {"title": 1, "user_id": 1,
                                                          "created_at": 1})]
    for d in docs:
        print(f"  {d.get('created_at')}  {d.get('user_id')}  {d.get('title')!r}")
    print(f"{len(docs)} empty conversation(s)")
    if delete and docs:
        res = await db["ai_conversations"].delete_many(empty)
        print(f"deleted {res.deleted_count}")
    elif docs:
        print("dry run — pass --delete to remove them")
    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main("--delete" in sys.argv))
