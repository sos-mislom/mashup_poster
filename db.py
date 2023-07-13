import aiomysql

async def create_pool(loop=None) -> aiomysql.Pool:
    return await aiomysql.create_pool(host='92.118.115.96', port=3306,
                                      user='monty', password='some_pass',
                                      db='mash_db', loop=loop,
                                      maxsize=10,
                                      autocommit=True)


