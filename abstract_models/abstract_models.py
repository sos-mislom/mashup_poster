import datetime
import json
from enum import Enum
from typing import List

import aiomysql

class DataBaseObject:
    TABLE_NAME = None
    SECRET_FIELDS = []

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, datetime.datetime):
                kwargs[k] = v.strftime('%d.%m.%Y %H:%M:%S')

        object.__setattr__(self, 'fields', kwargs)

    def __getattr__(self, item):
        return self.fields.get(item)

    def __setattr__(self, key, value):
        self.fields[key] = value

    def update_fields(self, fields: dict):
        object.__getattribute__(self, 'fields').update(fields)

    def _get_keys(self):
        return f"({', '.join(self.fields.keys())})"

    async def add(self,
                  cur: aiomysql.Cursor):
        sql = f"INSERT INTO `{self.TABLE_NAME}` {self._get_keys()} VALUES ({', '.join(['%s'] * len(self.fields))});"
        await cur.execute(
            sql,
            tuple(self.fields.values()))

        if not self.id:
            self.fields['id'] = cur.lastrowid

    async def get_one(self,
                      cur: aiomysql.Cursor,
                      limit: int = None,
                      offset: int = 0,
                      order: str = None) -> bool:
        sql = f"SELECT * FROM `{self.TABLE_NAME}`"
        if self.fields:
            sql += f" WHERE {' AND '.join(f'`{k}`=%s' for k in self.fields.keys())}"

        if order is not None:
            sql += f" {order}"

        if limit is not None:
            sql += f" LIMIT {offset}, {limit}"

        await cur.execute(sql, tuple(self.fields.values()))

        f = await cur.fetchone()
        if f is None:
            return False

        self.fields.update(**dict(f))
        return True

    async def get_many(self,
                       cur: aiomysql.Cursor,
                       limit: int = None,
                       offset: int = 0,
                       order: str = None) -> List[__name__]:
        sql = f"SELECT * FROM `{self.TABLE_NAME}`"

        if self.fields:
            sql += f" WHERE {' AND '.join(f'`{k}`=%s' for k in self.fields.keys())}"

        if order is not None:
            sql += f" {order}"

        if limit is not None:
            sql += f" LIMIT {offset}, {limit}"

        await cur.execute(sql, tuple(self.fields.values()))

        return [self.__class__(**dict(fields)) for fields in await cur.fetchall()]

    async def get_count(self,
                        cur: aiomysql.Cursor) -> int:
        sql = f"SELECT COUNT(*) as `count` FROM `{self.TABLE_NAME}`"
        if self.fields:
            sql += f" WHERE {' AND '.join(f'`{k}`=%s' for k in self.fields.keys())}"

        await cur.execute(sql,
                          tuple(self.fields.values()))

        fetched = await cur.fetchone()
        if 'count' not in fetched:
            return 0

        return fetched['count']

    async def sum(self,
                  cur: aiomysql.Cursor,
                  field_name: str) -> int:
        sql = f"SELECT SUM(`{field_name}`) as `sum` FROM `{self.TABLE_NAME}`"
        if self.fields:
            sql += f" WHERE {' AND '.join(f'`{k}`=%s' for k in self.fields.keys())}"

        await cur.execute(sql,
                          tuple(self.fields.values()))

        fetched = await cur.fetchone()
        if 'sum' not in fetched:
            return 0

        return fetched['sum']

    async def delete(self,
                     cur: aiomysql.Cursor):
        return await cur.execute(
            f"DELETE FROM `{self.TABLE_NAME}` WHERE {' AND '.join(f'`{k}`=%s' for k in self.fields.keys())};",
            tuple(self.fields.values())) > 0

    async def update(self,
                     cur: aiomysql.Cursor,
                     where_field: str = 'user_id'):
        return await cur.execute(
            f"UPDATE `{self.TABLE_NAME}` SET {', '.join(f'`{k}`=%s' for k in self.fields.keys())} "
            f"WHERE `{where_field}` = {self.fields.get(where_field)};",
            tuple(self.fields.values()))

    def __str__(self):
        return str(self.serialize(include_secret_fields=True))

    def serialize(self, include_secret_fields=False):
        if include_secret_fields:
            return self.fields

        return {k: v for k, v in self.fields.items() if k not in self.SECRET_FIELDS}

    def to_json(self, **kwargs):
        return json.dumps(self.serialize(**kwargs))

    def copy(self):
        return self.__class__(**self.serialize(include_secret_fields=True))

class Action(str, Enum):
    anek = "anek"
    save_to_chat = "save_to_chat"
    find_anek_by_tags = "find_anek_by_tags"
    to_tell_anek = "to_tell_anek"
    reset_all_ban_words = "reset_all_ban_words"
    meme = "meme"
    strawberry = "strawberry"
