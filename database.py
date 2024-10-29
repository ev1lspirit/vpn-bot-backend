import asyncio
import os
from functools import wraps, partial
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def make_async(function):
    @wraps(function)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        if not kwargs:
            return await loop.run_in_executor(None, function,  *args)
        return await loop.run_in_executor(None, partial(function, **kwargs), *args)
    return wrapper


class BaseConnectionState:
    pool = pool.SimpleConnectionPool(maxconn=10, minconn=2, user="postgres", password="roottoor", database="xclient")

    def __init__(self, db_name="postgres", db_user="postgres", host="127.0.0.1", port="5432", password="", use_dict_cursor=False):
        self.new_state(ClosedConnectionState)
        self.host = host
        self.port = port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = password
        self.use_dict_cursor = use_dict_cursor
        self.logger = logging.getLogger(self.__class__.__name__)
        self.conn = None
        self.cur = None
    def new_state(self, state):
        self.__class__ = state

    def conn_open(self):
        raise NotImplementedError

    def conn_close(self):
        raise NotImplementedError

    @make_async
    def select(self, query: str):
        raise NotImplementedError

    @make_async
    def execute(self, query: str, autocommit=True, returning=False):
        raise NotImplementedError

    def __enter__(self):
        raise RuntimeError("Can't use context manager with {self.__class__.__name__}".format(self=self))

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise RuntimeError("Can't use context manager with {self.__class__.__name__}".format(self=self))


class ClosedConnectionState(BaseConnectionState):

    def __enter__(self) -> BaseConnectionState:
        self.logger.debug("Connection to {name} has been opened!".format(name=self.db_name))
        self.conn_open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.debug("Connection to {name} has been closed!".format(name=self.db_name))
        self.conn_close()

    def conn_open(self):
        self.new_state(OpenConnectionState)
        self.conn = self.pool.getconn()
        '''pg.connect(host=self.host, port=self.port,
                                dbname=self.db_name, user=self.db_user, password=self.db_password)'''
        factory = None
        if self.use_dict_cursor:
            factory = RealDictCursor
        self.cur = self.conn.cursor(cursor_factory=factory)
        self.logger.info("Cursor for {name} is opened!".format(name=self.db_name))

    def conn_close(self):
        raise RuntimeError("Already closed!")


class OpenConnectionState(BaseConnectionState):

    def __init__(self, database=None, host=None, port=None, user=None, password=""):
        super().__init__(db_name=database, host=host, port=port, db_user=user, password=password)

    def conn_open(self):
        raise RuntimeError("Already open!")

    def conn_close(self):
        self.logger.debug("Cursor for {name} is closed!".format(name=self.db_name))
        self.pool.putconn(self.conn)
        # self.conn.close()
        self.conn, self.cur = None, None
        self.new_state(ClosedConnectionState)

    @make_async
    def select(self, query: str, *formats):
        logger.warning(formats)
        self.cur.execute(query, formats)
        self.logger.info(f"{query} executed.")
        result = self.cur.fetchall()
        self.logger.info(f"Query result: {result}")
        return result

    @make_async
    def execute(self, query: str, *formats, autocommit=False, returning=False):
        self.cur.execute(query, formats)
        self.logger.info(f"{query} executed.")
        ret = None
        if returning:
            ret = self.cur.fetchall()
        if autocommit:
            self.conn.commit()
            self.logger.info(f"{query} commited.")
        return ret


Database = partial(BaseConnectionState, password=os.getenv("password"))


