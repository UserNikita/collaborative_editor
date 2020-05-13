import jinja2
import aiohttp_jinja2
import aioredis
from aiohttp import web, WSCloseCode
from aiopg.sa import create_engine

from views import index, code_page, web_socket, user_list, generate_page
from storage import create_tables
from settings import *


async def engine_ctx(app):
    app['engine'] = await create_engine(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DATABASE,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    async with app['engine'].acquire() as conn:
        await create_tables(conn)
    yield
    app['engine'].close()
    await app['engine'].wait_closed()


async def redis_ctx(app):
    app['redis'] = await aioredis.create_connection((REDIS_HOST, REDIS_PORT), password=REDIS_PASSWORD)
    yield
    app['redis'].close()
    await app['redis'].wait_closed()


async def on_startup(app):
    app['ws'] = {}
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(TEMPLATE_DIR))


async def on_shutdown(app):
    for ws_by_page in app['ws'].values():
        for ws in ws_by_page.values():
            await ws.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown')


def main():
    app = web.Application()

    routes = [
        web.static('/static', STATIC_DIR),
        web.get('/generate', generate_page, name='generate_page'),
        web.get('/{key}/users/', user_list, name='user_list'),
        web.get('/{key}/ws', web_socket, name='ws'),
        web.get('/{key}', code_page, name='code_page'),
        web.get('/', index, name='index'),
    ]
    app.add_routes(routes=routes)

    app.on_startup.append(on_startup)
    app.cleanup_ctx.append(engine_ctx)
    app.cleanup_ctx.append(redis_ctx)
    app.on_cleanup.append(on_shutdown)

    web.run_app(app, port=PORT)


if __name__ == '__main__':
    main()
