#! /usr/bin/env python3
from bs4 import BeautifulSoup  # type: ignore
from db import Database
from pathlib import Path
from queue import Queue
from subprocess import Popen, PIPE
from threading import Thread
from typing import Tuple, List, Any

import argparse
import configparser
import http.client
import json
import os
import re
import sys
import urllib.request as request


ConfigSection = configparser.SectionProxy
Response = http.client.HTTPResponse
Request = request.Request


class Updater:
    def __init__(self,
                 database: Database,
                 maxthreads: int = 10):
        self.maxthreads: int = maxthreads
        self.db: Database = database

        self.db.cur.execute('SELECT id FROM posts')
        local_latest: int
        try:
            local_latest = max([r[0] for r in self.db.cur.fetchall()])
        except ValueError:  # empty
            local_latest = 0
        remote_latest: int = self.get_remote_latest()
        self.new_posts: List[int] = [
                i for i in range(local_latest, remote_latest + 1)
                ]

    def get_remote_latest(self) -> int:
        print('更新文章列表...')
        user_agent: str = ('Mozilla/5.0 (X11; Linux x86_64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/92.0.4515.159 Safari/537.36')
        req: Request = request.Request(url='https://finfo.tw/posts',
                                       headers={'User-Agent': user_agent},
                                       method='GET')
        response: Response = request.urlopen(req)

        if response.status == 200:
            page: str = response.read().decode('utf8')
        else:
            print('無法更新聞章列表，請稍後再試。')
            sys.exit(1)

        soup: BeautifulSoup = BeautifulSoup(page, 'html.parser')
        class_: str = ('text-decoration-none d-flex '
                       'justify-content-center row')
        latest_post = soup.find('a', class_=class_)

        return int(latest_post['href'].split('/')[-1])

    def parse(self, json_data) -> Tuple[list, list]:
        TOPICS: List[str] = ['投保規劃', '保單健檢', '理賠申請',
                             '保單解約', '保險觀念']
#        REGIONS: List[str] = ['北部', '中部', '南部', '東部']

        self.db.cur.execute('SELECT id FROM users')
        AUTHOR_ID_BASE: int
        try:
            AUTHOR_ID_BASE = max([r[0] for r in self.db.cur.fetchall()])
        except ValueError:
            AUTHOR_ID_BASE = 0

        try:
            data: dict = json.loads(json_data)['articles'][0]
        except json.decoder.JSONDecodeError:  # post not exists anymore
            return None

        post_id: int = data['id']
        title: str = data['title']
        topic_id: int = TOPICS.index(data['class']) + 1  # db count from 1
        # finfo.tw start at 2021, it's safe to hard code year till 2022...
        datetime: str = '2021-' + '-'.join(data['dateTime'].split('/'))
        author_name: str = data['author']['userName']
        author_type: str = data['author']['identity']
        content: str = data['content']
        replies: List[dict] = data['replies']

        posts: list = []
        users: list = []

        users.append((author_name, author_type == 'insurer'))
        #                             ↓ 0 means oringinal post, not a reply
        posts.append((post_id, title, 0, datetime,
                      AUTHOR_ID_BASE + len(users), topic_id, content))

        for reply in replies:
            users.append((reply['author']['userName'],
                          reply['author']['identity'] == 'insurer'))
            posts.append((reply['belongsTo'],
                          title,
                          reply['floor'],
                          '2021-' + '-'.join(reply['dateTime'].split('/')),
                          AUTHOR_ID_BASE + len(users),
                          topic_id,
                          reply['content']))

        return posts, users

    def start(self):
        if not any(self.new_posts):
            print('資料庫以為最新狀態，無須更新')
            sys.exit(0)

        json_queue: Queue = Queue()  # json string - str
        threads: List[Thread] = [DataPorter(self.new_posts, json_queue)
                                 for _ in range(self.maxthreads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        posts: List[tuple] = []
        users: List[tuple] = []
        while not json_queue.empty():
            tmp: Tuple[List[Any], List[Any]] = self.parse(json_queue.get())
            posts += [*tmp[0]]
            users += [*tmp[1]]

        self.db.insert('users', users)
        self.db.insert('posts', posts)

        print('\n全部工作皆已完成，資料庫為最新狀態\n')


class DataPorter(Thread):
    '''Consumes post index in in_queue, get data from remote, then put
    gathered data into out_queue.
    '''
    def __init__(self, indices: List[int], out_queue: Queue):
        super().__init__()
        self.job_not_done: List[int] = indices
        self.out_queue: Queue = out_queue

    def run(self):
        while any(self.job_not_done):
            index: int = self.job_not_done.pop()
            print(f'DataPorter: 抓取文章 {index} ...')
            args: list = ['python3', 'finfo_view.py',
                          '--nosave', '--json', '--index', str(index)]
            proc = Popen(args, stdout=PIPE)
            out, err = proc.communicate()

            out = out.decode('utf8')

            if '文章不存在或已被刪除' in out:
                print(f'DataPorter: 文章 {index} 不存在或已被刪除')
            else:
                self.out_queue.put(out)
                print(f'DataPorter: 文章 {index} 已擷取至本地端')


def main():
    argpsr = argparse.ArgumentParser(description='更新資料庫')
    argpsr.add_argument('-f', '--file',
                        help='使用指定的設定文件',
                        nargs=1, metavar='文件路徑')
    argpsr.add_argument('-t', '--threads',
                        help='同時間最大執行緒數目（預設：10）',
                        nargs=1, metavar='N',
                        type=int, default=10)

    module_dir: Path = Path(sys.modules['db'].__file__).parent.resolve()

    args = argpsr.parse_args()

    cfg_path: Path
    if args.file:
        cfg_path = Path(args.file).resolve()
    else:
        cfg_path = module_dir / 'config.cfg'

    config = configparser.ConfigParser(allow_no_value=True)
    config.SECTCRE = re.compile(r"\[ *(?P<header>[^]]+?) *\]")
    config.read(cfg_path, encoding='utf-8-sig')
    cfg: ConfigSection = config['UPDATE']

    database: Database = Database(str(cfg_path))

    maxthreads: int
    if args.threads != 10:
        maxthreads = args.threads
    elif cfg['maxthreads']:
        maxthreads = cfg.getint('maxthreads')
    else:
        maxthreads = 10

    os.chdir(module_dir)

    updater: Updater = Updater(database=database, maxthreads=maxthreads)
    updater.start()


if __name__ == "__main__":
    main()
