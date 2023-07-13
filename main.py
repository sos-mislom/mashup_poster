import asyncio
import logging
import re

import aioschedule
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import *

import config
from api import api_vk_user
from models.models import Post
from db import *

storage = MemoryStorage()

dp = Dispatcher(storage=storage)
bot = Bot(token=config.TOKEN_TG)

async def scheduler():
    aioschedule.every(60).seconds.do(wall_parser_mashup)
    aioschedule.every(90).seconds.do(wall_parser_mashup_hk)
    aioschedule.every(120).seconds.do(wall_parser_my)

    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def main():
    asyncio.create_task(scheduler())

    logging.warning("Стартуем!! СТАРТУЕММ!!")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def wall_parser_mashup():
    await wall_parser_('mashup')


async def wall_parser_mashup_hk():
    await wall_parser_('mashuphk')


async def wall_parser_my():
    await wall_parser_('hihanka')


async def wall_parser_(domain: str):
    mashup_parser = api_vk_user.MashupAPI(
            config.VK_TOKEN,
            config.APP_ID,
            config.USER_ID
        )

    post = await mashup_parser.get_posts(domain=domain)

    pool = await create_pool()

    if post['response'] and len(post := post['response']['items']) > 0:
        post = post[0]

        post_db = Post(
            post_id=post['id'],
            group_id=post['owner_id'])

        async with pool.acquire() as conn, conn.cursor(aiomysql.cursors.DictCursor) as cur:
            if await post_db.get_one(cur):
                await mashup_parser.session.close()
                return

        await bot.send_message(config.SEND_TO_ADMIN, text=f"Нашел новый пост {post['id']} {post['owner_id']}")

        message_text = ""
        if post['text']: message_text = post['text']

        attachments = []
        if post['attachments']: attachments = post['attachments']

        photo_urls = []
        audio_list = []

        for att in attachments:
            if att['type'] == 'photo':
                photo_urls.append(
                    att['photo']["sizes"][-1]["url"]
                )
            elif att['type'] == 'audio':
                audio_list.append({
                    'artist': att['audio']['artist'],
                    'title': att['audio']['title'],
                    'duration': att['audio']['duration'],
                    'url': att['audio']['url'].split("?siren=1")[0]
                })

        media_photo = []
        media_audio = []


        for photo_url in photo_urls:
            media_photo.append(InputMediaPhoto(media=photo_url,
                                               caption=message_text)
                               )

        try:
            for aud in audio_list:
                file_name = clear_name(f"{aud['title']}-{aud['artist']}")

                music_downloader = api_vk_user.MusicDownloader()
                binary_data = await music_downloader.download_by_m3u8_url(aud)

                if binary_data:
                    audio = BufferedInputFile(file=binary_data,
                                              filename=file_name+".mp3"
                                              )

                    media_audio.append(InputMediaAudio(media=audio,
                                                       title=aud['title'],
                                                       performer=aud['artist']
                                                       )
                                       )
        except Exception as e:
            # ++ Ошибки мне в лс
            await bot.send_message(config.SEND_TO_ADMIN, text=str(e))
            await mashup_parser.session.close()
            return

        async with pool.acquire() as conn, conn.cursor(aiomysql.cursors.DictCursor) as cur:
            if not await post_db.get_one(cur):
                await post_db.add(cur)

                await bot.send_message(config.SEND_TO_ADMIN, text=f"Добавляю пост {post['id']} {post['owner_id']}")

                try:
                    # ++ Сам мешап
                    await bot.send_media_group(config.GROUP_TO_SEND, media_photo)
                    await bot.send_media_group(config.GROUP_TO_SEND, media_audio)

                except Exception as e:
                    # ++ Ошибки мне в лс
                    await bot.send_message(config.SEND_TO_ADMIN, text=str(e))
    await mashup_parser.session.close()


def clear_name(docname,
               slash_replace='-',
               quote_replace='',
               multispaces_replace='\x20',
               quotes="""“”«»'\""""
               ):
    docname = re.sub(r'[' + quotes + ']', quote_replace, docname)
    docname = re.sub(r'[/]', slash_replace, docname)
    docname = re.sub(r'[|*?<>:\\\n\r\t\v]', '', docname)
    docname = re.sub(r'\s{2,}', multispaces_replace, docname)
    docname = docname.strip()
    docname = docname.rstrip('-')
    docname = docname.rstrip('.')
    docname = docname.strip()
    return docname

if __name__ == '__main__':
    asyncio.run(main())
