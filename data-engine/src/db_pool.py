"""
UNS Data Engine — DB Connection Pool

使用 psycopg2.pool.ThreadedConnectionPool 管理連線池。
提供 connection() context manager 並處理斷線重連。
"""

import contextlib
import logging
from typing import Generator

import psycopg2
import psycopg2.pool

from .config import Config

logger = logging.getLogger("uns.db_pool")

class DBPool:
    """
    資料庫連線池封裝。
    
    支援 ThreadedConnectionPool 並實作基礎的自動重連邏輯。
    """
    def __init__(self):
        self._pool = None
        self._dsn = Config.db_dsn()
        self._min_conn = Config.DB_POOL_MIN
        self._max_conn = Config.DB_POOL_MAX
        self._init_pool()

    def _init_pool(self):
        """初始化或重新建立連線池。"""
        try:
            logger.info("Initializing DB connection pool (%d-%d connections)...", self._min_conn, self._max_conn)
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                self._min_conn,
                self._max_conn,
                **self._dsn
            )
            logger.info("DB connection pool initialized")
        except psycopg2.Error as e:
            logger.error("Failed to initialize DB pool: %s", e)
            self._pool = None

    def _ensure_pool(self):
        """確保連線池存在，若不存在則嘗試重建。"""
        if self._pool is None:
            self._init_pool()
        if self._pool is None:
            raise psycopg2.OperationalError("Database pool is not available")

    @contextlib.contextmanager
    def connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        取得連線的 Context Manager。
        
        Usage:
            with db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(...)
                conn.commit()
        """
        self._ensure_pool()
        conn = None
        try:
            conn = self._pool.getconn()
            # 檢查連線是否仍然有效 (psycopg2 不會自動檢查)
            if conn.closed:
                logger.warning("Acquired a closed connection from pool, trying to reconnect...")
                self._pool.putconn(conn, close=True)
                conn = self._pool.getconn()
            
            yield conn
            
        except psycopg2.OperationalError as e:
            logger.error("Database operational error: %s", e)
            if conn:
                self._pool.putconn(conn, close=True)
                conn = None
            # 如果是嚴重錯誤，可能需要標記連線池失效
            if "connection already closed" in str(e).lower() or "terminated" in str(e).lower():
                 logger.warning("Detected broken pool, will attempt re-init on next call")
                 self._pool = None
            raise
        except Exception:
            if conn:
                # 發生其他例外時，rollback 並放回池中
                try: conn.rollback()
                except: pass
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def close(self):
        """關閉所有連線。"""
        if self._pool:
            logger.info("Closing DB connection pool...")
            self._pool.closeall()
            self._pool = None
