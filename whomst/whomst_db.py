import sqlite3
import os
import datetime


DB_NAME = 'whomst.db'
DB_SCHEMA = 'whomst.sql'


class Whomst(object):
    def __init__(self, root_dir):
        self.root_dir = root_dir


    def get_db_connection(self):
        conn =  sqlite3.connect(os.path.join(self.root_dir, DB_NAME),
                                detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn


    def setup_database(self):
        conn = self.get_db_connection()

        with conn:
            cur = conn.cursor()
            with open(os.path.join(self.root_dir, DB_SCHEMA), 'r') as sql_file:
                cur.execute(sql_file.read())

        conn.commit()
        conn.close()


    def whomst(self, display_name, connect_code, ip_address, region):
        conn = self.get_db_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO whomst(display_name, connect_code, ip_address, region, time_added)
                VALUES(?, ?, ?, ?, ?)
                """,
                (display_name, connect_code, ip_address, region, datetime.datetime.now())
            )
        conn.commit()
        conn.close()


    def fetch(self, limit=10):
        conn = self.get_db_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT display_name, connect_code, ip_address, region, time_added
                FROM whomst
                ORDER BY time_added DESC
                LIMIT ?
                """, (str(limit),));
            rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]


    def fetch_by_ip_address(self, ip_address, mask=32, limit=100):
        assert(mask in [8, 16, 24, 32])
        search_ip_address = '.'.join(ip_address.split('.')[:(mask//8)])

        conn = self.get_db_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT display_name, connect_code, ip_address, region, time_added
                FROM whomst
                WHERE ip_address LIKE ?
                ORDER BY time_added DESC
                LIMIT ?
                """, (search_ip_address + '%', str(limit)));
            rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
