import os
import re

import yt_dlp as youtube_dl
from aiogram.types import InputMediaVideo
from aiogram.types import BufferedInputFile
from aiogram.types import InputMediaAudio
from aiogram.types import FSInputFile
from aiogram.types import InputMediaPhoto

from api import api_vk_user
from config import DEFAULT_SAVE_DIR


def download_photo_input_media(photo_urls) -> list:
    media_photo = []
    for url in photo_urls:
        media_photo.append(InputMediaPhoto(media=url))
    return media_photo

def longer_than_five_minute(info, *, incomplete):
    duration = info.get('duration')
    if duration and duration > 60*5:
        return 'The video is too long'


def download_video_input_media(video_urls) -> (list, list):
    to_del, media_video = [], []

    ydl_opts = {
        'match_filter': longer_than_five_minute,
        'outtmpl': DEFAULT_SAVE_DIR,
        'quiet': True
    }
    for url in video_urls:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download((url['url'],))

        from os import listdir
        from os.path import isfile, join
        onlyfiles = [f for f in listdir(r"/root/mashup_poster_bot/music/") if isfile(join(r"/root/mashup_poster_bot/music/", f))]

        for file_path in onlyfiles:
            if ".mp4" in file_path or ".mkv" in file_path or ".webm" in file_path:
                to_del.append(r"/root/mashup_poster_bot/music/" + file_path)
                media_video.append(InputMediaVideo(
                    media=FSInputFile(path=r"/root/mashup_poster_bot/music/" + file_path,
                                      filename="file.mp4"),
                    supports_streaming=True,
                ))
    return to_del, media_video


async def download_audio_input_media(audio_urls) -> list:
    media_audio = []
    for aud in audio_urls:
        file_name = clear_name(f"{aud['title']}-{aud['artist']}")

        music_downloader = api_vk_user.MusicDownloader()
        binary_data = await music_downloader.download_by_m3u8_url(aud)

        if binary_data:
            audio = BufferedInputFile(file=binary_data,
                                      filename=file_name
                                      )
            media_audio.append(InputMediaAudio(
                media=audio,
                title=aud['title'] + ".mp3",
                performer=aud['artist'],
                duration=aud['duration'])
            )
    return media_audio

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
