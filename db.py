import aiomysql

async def create_pool(loop=None) -> aiomysql.Pool:
    return await aiomysql.create_pool(host='', port=3306,
                                      user='', password='',
                                      db='mash_db', loop=loop,
                                      maxsize=10,
                                      autocommit=True)


