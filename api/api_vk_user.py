import asyncio
import os
import threading
from asyncio import wait_for, gather, Semaphore

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

from aiohttp import ClientSession
import aiohttp
import m3u8
import requests
from config import *


class MashupAPI:
    def __init__(self,
                 api_token: str,
                 app_id: int,
                 user_id: int):

        self.app_id = app_id
        self.uid = user_id

        self.session = aiohttp.ClientSession(headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'multipart/form-data'
        })

    async def get_posts(self, domain: str, count: int = 1, offset: int = 1):
        async with self.session.post(
                f'https://api.vk.com/method/wall.get?v=5.107&domain={domain}&offset={offset}&count={count}'
        ) as response:
            return await response.json()


class MusicDownloader:
    def __init__(self):
        pass

    async def download_by_m3u8_url(self, m3u8_url):
        """Загрузка и сохранение аудио по m3u8 ссылке"""
        m3u8_url=m3u8_url['url']

        m3u8_data = m3u8.load(uri=m3u8_url)
        parsed_m3u8 = self._parse_m3u8(m3u8_data)
        segments_binary_data = await self._get_audio_from_m3u8(parsed_m3u8=parsed_m3u8, m3u8_url=m3u8_url)

        return segments_binary_data


    @staticmethod
    def _parse_m3u8(m3u8_data):
        """Возвращает информацию о сегментах"""
        parsed_data = []
        segments = m3u8_data.data.get("segments")
        for segment in segments:
            temp = {"name": segment.get("uri")}

            if segment["key"]["method"] == "AES-128":
                temp["key_uri"] = segment["key"]["uri"]
            else:
                temp["key_uri"] = None

            parsed_data.append(temp)
        return parsed_data

    @staticmethod
    def _download_content(url: str) -> bytes:
        response = requests.get(url=url)
        return response.content if response.status_code == REQUEST_STATUS_CODE else None

    async def _get_audio_from_m3u8(self, parsed_m3u8: list, m3u8_url: str) -> bytes:
        """Асинхронно скачивает сегменты и собирает их в одну байт-строку"""
        downloaded_chunks = [None] * len(parsed_m3u8)
        semaphore = Semaphore(MAX_TASKS)

        async def download():
            tasks = []
            async with ClientSession() as session:
                for index, segment in enumerate(parsed_m3u8):
                    tasks.append(
                        wait_for(
                            handle_segment(segment, index, session),
                            timeout=MAX_TIME
                        )
                    )
                return await gather(*tasks)

        async def handle_segment(segment: dict, segment_index: int, session: ClientSession) -> None:
            segment_uri = m3u8_url.replace("index.m3u8", segment["name"])
            content = await download_chunk(segment_uri, session)

            if segment["key_uri"] is not None:
                key = await download_chunk(segment["key_uri"], session)
                content = await decode_aes_128(data=content, key=key)

            downloaded_chunks[segment_index] = content

        async def download_chunk(url: str, session: ClientSession) -> bytes:
            async with semaphore:
                async with session.get(url) as res:
                    content = await res.read()
                    return content if res.status == REQUEST_STATUS_CODE else None

        async def decode_aes_128(data: bytes, key: bytes) -> bytes:
            """Декодирование из AES-128 по ключу"""
            try:
                iv = data[0:16]
            except TypeError:
                return bytearray()
            ciphered_data = data[16:]
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            decoded = unpad(cipher.decrypt(ciphered_data), AES.block_size)
            return decoded

        await download()

        return b''.join(downloaded_chunks)

    @staticmethod
    def _write_to_file(data: bytes, path: str):
        with open(path, "wb+") as f:
            f.write(data)
