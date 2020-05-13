import datetime
import random

import sqlalchemy as sa
from sqlalchemy.sql.ddl import CreateTable

metadata = sa.MetaData()


pages = sa.Table(
    'pages', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('key', sa.String(6), nullable=False, unique=True),
    sa.Column('code', sa.Text),
    sa.Column('language', sa.String(255)),
    sa.Column('created_at', sa.DateTime),
    sa.Column('updated_at', sa.DateTime),
)


async def create_tables(conn):
    await conn.execute('DROP TABLE IF EXISTS pages')
    await conn.execute(CreateTable(pages))


async def get_stats(conn):
    query = pages.select().with_only_columns([pages.c.language, sa.func.count(pages.c.id)]).group_by(pages.c.language)
    stats = [{'lang': row[0], 'count': row[1]} async for row in await conn.execute(query)]
    return stats


async def get_code_page(conn, key):
    page = await (await conn.execute(pages.select().where(pages.c.key == key))).first()
    return page


async def save_code_page(conn, key, *, code=None, language=None):
    values = {}
    if code is not None:
        values['code'] = code
    if language is not None:
        values['language'] = language

    if await get_code_page(conn, key):
        query = pages.update().where(pages.c.key == key).values(
            updated_at=datetime.datetime.now(),
            **values
        )
        await conn.execute(query)
    else:
        query = pages.insert().values(
            key=key,
            created_at=datetime.datetime.now(),
            **values
        )
        await conn.execute(query)


async def get_all_users(redis, page_key):
    page = 'page:%s' % page_key
    keys_and_values = await redis.execute('HGETALL', page)
    users = [(keys_and_values[i].decode(), keys_and_values[i+1].decode())
             for i in range(0, len(keys_and_values), 2)]
    return users


async def set_user_name(redis, page_key, user_id, name):
    page = 'page:%s' % page_key
    await redis.execute('HSET', page, user_id, name)


async def get_user_id(redis, page_key):
    page = 'page:%s' % page_key
    users_id = {int(i) for i in await redis.execute('HKEYS', page)}
    user_id = random.choice(tuple(set(range(len(users_id) + 5)) - users_id))
    redis.execute('HSET', page, user_id, '')  # Нужно занять этот id в хэше
    return user_id


async def delete_user(redis, page_key, user_id):
    page = 'page:%s' % page_key
    await redis.execute('HDEL', page, user_id)
