from typing import Mapping, List, Tuple, Any, Set

import configparser
import mariadb  # type: ignore
import re
import sys


ConfigSection = configparser.SectionProxy


class Database:
    def __init__(self, config_path: str):
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.SECTCRE = re.compile(r"\[ *(?P<header>[^]]+?) *\]")
        parser.read(config_path, encoding='utf-8-sig')
        cfg: ConfigSection = parser['DATABASE']

        self._not_select_db: bool = False
        login_opts = self._parse_login_opts(cfg, parser.BOOLEAN_STATES)

        try:
            self.conn = mariadb.connect(**login_opts)
        except mariadb.Error as e:
            print('\nMariaDB:', e)
            print('Finfo-update: Unable to login into database.\n')
            sys.exit(1)

        self.cur = self.conn.cursor()

        if self._not_select_db:
            try:
                self.cur.execute('USE finfo')
            except mariadb.OperationalError:  # database not exist
                self.cur.execute('CREATE DATABASE finfo')
                self.init_database()

    def _parse_login_opts(self,
                          cfg: ConfigSection,
                          boolean_states: Mapping[str, bool]) -> dict:
        login_opts: dict = {k: (v
                                if v not in boolean_states
                                else boolean_states[v])
                            for k, v in zip(cfg.keys(), cfg.values())}

        if 'user' not in login_opts or (login_opts['user'] is None):
            login_opts['user'] = 'py-finfo'

        if 'host' not in login_opts or (login_opts['host'] is None):
            login_opts['host'] = 'localhost'

        if 'port' not in login_opts or (login_opts['port'] is None):
            login_opts['port'] = 3306
        login_opts['port'] = int(login_opts['port'])

        if login_opts['passwd'] is None:
            del login_opts['passwd']

        if login_opts['database'] is None:
            del login_opts['database']
            self._not_select_db = True

        login_opts['autocommit'] = True

        return login_opts

    def init_database(self):
        '''Delete any table stored in finfo, then initializing anything.'''
        with open('schema.sql') as file:
            script: str = file.read()

        for statement in script.split(';'):
            try:
                self.cur.execute(statement)
            except mariadb.ProgrammingError:  # statement = '\n'
                continue

    def insert(self, tbl_name: str, vals: List[Tuple[Any]]):
        statement: str = {
                'posts': ('INSERT INTO posts (post_id, title, position, '
                          'create_time, author_id, topic_id, content) '
                          'VALUES (?, ? ,?, ?, ?, ?, ?)'),
                'users': ('INSERT INTO users (name, insurer_or_salesman) '
                          'VALUES (?, ?)')
                }[tbl_name]

        if tbl_name == 'posts':
            self.cur.executemany(statement, vals)
        else:  # tbl_name == 'users'
            new_users: Set[Tuple[Any]] = set()  # ensure uniqueness
            for u in vals:
                existed: bool
                if u[0].endswith('*'):  # insurer
                    existed = False
                else:
                    self.cur.execute('SELECT name FROM users;')
                    existed = u[0] in [r[0] for r in self.cur.fetchall()]

                if not existed:
                    new_users.add(u)

            self.cur.executemany(statement, vals)

    def update(self):
        ...
