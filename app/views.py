import string
import random
import asyncio

import aiohttp_jinja2
from aiohttp import web

from storage import (
    save_code_page,
    get_code_page,
    get_user_id,
    set_user_name,
    get_all_users,
    delete_user,
    get_stats
)


async def index(request):
    async with request.app['engine'].acquire() as conn:
        stats = await get_stats(conn)
    return aiohttp_jinja2.render_template('index.html', request, {'stats': stats})


async def generate_page(request):
    random_string = ''.join(random.choice(string.ascii_lowercase) for i in range(6))
    location = request.app.router['code_page'].url_for(key=random_string)
    return web.HTTPFound(location=location)


async def code_page(request):
    page_key = request.match_info.get('key')
    async with request.app['engine'].acquire() as conn:
        page = await get_code_page(conn, key=page_key)
    users = await get_all_users(request.app['redis'], page_key=page_key)

    context = {'page': page, 'key': page_key, 'users': users}
    return aiohttp_jinja2.render_template('page.html', request, context)


async def user_list(request):
    page_key = request.match_info.get('key')
    users = await get_all_users(request.app['redis'], page_key=page_key)
    return web.json_response(users)


async def web_socket(request):
    current_ws = web.WebSocketResponse()
    await current_ws.prepare(request)

    page_key = request.match_info.get('key')
    user_id = await get_user_id(request.app['redis'], page_key)
    await current_ws.send_json({'event': 'setUserId', 'value': user_id})

    if page_key in request.app['ws']:
        request.app['ws'][page_key][user_id] = current_ws
    else:
        request.app['ws'][page_key] = {user_id: current_ws}

    try:
        async for msg in current_ws:
            if msg.type == web.WSMsgType.text:
                data = msg.json()
                data['userId'] = user_id
                event = data.get('event')

                if event == 'join':
                    await set_user_name(request.app['redis'], page_key=page_key, user_id=user_id, name=data['value'])

                elif event == 'update':
                    async with request.app['engine'].acquire() as conn:
                        await save_code_page(conn, key=page_key, code=data['value'])

                elif event == 'changeLanguage':
                    async with request.app['engine'].acquire() as conn:
                        await save_code_page(conn, key=page_key, language=data['value'])

                elif event == 'changeUsername':
                    await set_user_name(request.app['redis'], page_key=page_key, user_id=user_id, name=data['value'])

                # Отправить событие остальным участникам
                for ws in request.app['ws'][page_key].values():
                    if ws is not current_ws:  # Кроме пользователя создавшего событие
                        await ws.send_json(data)
    except asyncio.CancelledError:  # Перехват разрыва соединения инициированного клиентом
        pass
    finally:
        # Заметаем следы присутствия пользователя в системе
        del request.app['ws'][page_key][user_id]
        await delete_user(request.app['redis'], page_key, user_id)
        # Сообщаем всем, что пользователь покинул страницу
        for ws in request.app['ws'][page_key].values():
            await ws.send_json({'event': 'leave', 'userId': user_id})

    return current_ws
