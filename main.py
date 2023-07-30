import asyncio
import logging

import aioschedule
from aiogram import Bot
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from db import *
from input_media_loader import *
from keybord.inline_buttons import *
from models.models import Post

storage = MemoryStorage()

dp = Dispatcher(storage=storage)
bot = Bot(token=config.TOKEN_TG)


async def scheduler():
    aioschedule.every(60).seconds.do(wall_parser_my)
    aioschedule.every(90).seconds.do(wall_parser_mashup)
    aioschedule.every(120).seconds.do(wall_parser_mashup_hk)

    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def main():
    asyncio.create_task(scheduler())

    logging.warning("Мэшапы ищуцца...")

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

        message_text = ""
        if post['text']: message_text = telegram_text_formatter(post['text'])

        attachments = []
        if post['attachments']: attachments = post['attachments']

        photo_urls = []
        audio_urls = []
        video_urls = []

        for att in attachments:
            if att['type'] == 'photo':
                photo_urls.append(
                    att['photo']["sizes"][-1]["url"]
                )

            elif att['type'] == 'audio':
                audio_urls.append({
                    'artist': att['audio']['artist'],
                    'title': att['audio']['title'],
                    'duration': att['audio']['duration'],
                    'url': att['audio']['url'].split("?siren=1")[0]
                })
            elif att['type'] == 'video':
                video_id = str(att['video']['owner_id']) + "_" + str(att['video']['id'])
                video_info = (await mashup_parser.get_video(video_id))

                if video_info['response'] and len(video_info := video_info['response']['items']) > 0:
                    video_info = video_info[0]
                    video_urls.append({
                        'url': video_info['player'],
                    })
            else:
                await bot.send_message(config.SEND_TO_ADMIN, text=f"Добавь {att['type']}")

        to_del = []

        media_photo = download_photo_input_media(photo_urls)

        to_del, media_video = download_video_input_media(video_urls)

        media_audio = await download_audio_input_media(audio_urls)

        keybord_ = post_markup(
            f"https://vk.com/wall{post['owner_id']}_{post['id']}"
        ).as_markup()

        async with pool.acquire() as conn, conn.cursor(aiomysql.cursors.DictCursor) as cur:
            if not await post_db.get_one(cur):
                await post_db.add(cur)
                try:
                    if len(media_photo) > 1:
                        await bot.send_media_group(config.GROUP_TO_SEND, media_photo)
                        await bot.send_message(config.GROUP_TO_SEND,
                                               text=message_text if len(message_text)> 0 else "В посте нет текста, а кнопку выводить нужно",
                                               reply_markup=keybord_,
                                               parse_mode='HTML')
                    elif len(media_photo) > 0:
                        await bot.send_photo(config.GROUP_TO_SEND,
                                             photo=photo_urls[0],
                                             caption=message_text,
                                             reply_markup=keybord_,
                                             parse_mode='HTML')
                    else:
                        if len(media_video) > 1:
                            await bot.send_media_group(config.GROUP_TO_SEND, media_video)
                            await bot.send_message(config.GROUP_TO_SEND,
                                                   text=message_text if len(message_text)>0 else "В посте нет текста, а кнопку выводить нужно",
                                                   reply_markup=keybord_,
                                                   parse_mode='HTML')
                        elif len(media_video) > 0:
                            await bot.send_video(config.GROUP_TO_SEND,
                                                 video=FSInputFile(to_del[0],
                                                      filename="file.mp4"),
                                                 supports_streaming = True,
                                                 caption=message_text,
                                                 reply_markup=keybord_,
                                                 parse_mode='HTML'
                                             )
                        else:
                            await bot.send_message(config.GROUP_TO_SEND,
                                                   text=message_text if len(
                                                       message_text) > 0 else "В посте нет текста, а кнопку выводить нужно",
                                                   reply_markup=keybord_,
                                                   parse_mode='HTML')
                    if len(media_audio) > 0:
                        await bot.send_media_group(config.GROUP_TO_SEND, media_audio)

                except Exception as e:
                    [os.remove(x) for x in to_del]
                    await bot.send_message(config.SEND_TO_ADMIN, text=str(e))
                    await mashup_parser.session.close()
                    return
        [os.remove(x) for x in to_del]
    await mashup_parser.session.close()

def telegram_text_formatter(input_string):
    pattern = r"\[([^\]]+)\|([^\]]+)\]"
    def replace_match(match):
        return f'<a href="https://vk.com/{match.group(1)}">{match.group(2)}</a>'

    return re.sub(pattern, replace_match, input_string)


if __name__ == '__main__':
    asyncio.run(main())
