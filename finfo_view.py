#! /usr/bin/env python3
'''
FINFO 貼文簡易查詢

功能：
互動式 finfo.tw 討論區貼文查看器。

這支程式只做兩件事：
1. 對話式的印出指定文章的內容（由文章編號指定）
2. 把查詢過的文章存入硬碟（ JSON ）

使用方式：
$ python finfo_view.py [-h|--help] [-o|--output PATH] [-n|--nosave]
                       [-j|--json] [-i|--index INDEX]

選項：
-h, --help               印出這份文件並退出
-o PATH, --ouptput PATH  指定輸出 JSON 檔的位置，包含檔案名稱及副檔名
                        （預設於工作目錄下存檔）
-n, --nosave             無論如何都不要存檔
-j, --json               改成印出 JSON 格式文字
-i INDEX, --index INDEX  由文章編號擷取指定的一篇文章並退出，
                         文章編號須為正整數

需求：
- python3.x.x
- bs4
- requests

原作者：kent800821@gmail.com
專案負責人：zheruiyang@gmail.com 楊哲睿（Zhe-Rui, Yang）
'''

# 存入硬碟的 JSON 檔結構：
# json_:
#   - 描述
#     概念上的資料庫本身，內含三個資料表。分別為：
#     * articles: 裝載查詢過的文章的串列，每個串列元素是一篇文章，
#                 詳見下方 article
#     * replies: 裝載查詢過所有文章內所有回應的串列，每個串列元素是一篇回應
#                ，詳見下方 reply
#     * classes: 文章分類，是個字串串列、長度固定
#     * users: 裝載查詢過的文章和其回應中的作者群串列，
#                每個串列元素是一位作者，詳見下方 users
#
#     articles 與 users 的每個元素視為慨念上的資料列
#
#   - 結構
#     {
#       'articles': [article_1,
#                    article_2, ...],
#       'replies': [reply_1,
#                   reply_2, ...],
#       'classes': ['投保規劃', '保單健檢', '理賠申請',
#                   '理賠申請', '保險觀念'],
#       'users': [user_1,
#                 user_2, ...]
#     }
#
# article:
#   - 描述
#     描述文章本身的字典，每個鍵值為相對應的欄位
#   - 結構
#     {
#       'id: int,         # 文章在網站上獨一無二的識別號碼
#       'title': str,     # 文章標題
#       'class': str,     # 文章分類
#       'dateTime': str,  # 發文時間、日期
#       'author': dict,   # 描述作者的一個字典
#       'content': str,   # 內文
#       'replies': list   # 包含本篇文章所有回應的串列，詳見下方 reply
#     }
#
# reply:
#  - 描述
#    描述一篇文章中的其中一個回應的字典，每個鍵值為相對應的欄位
#    已刪除的回應會被忽略
#  - 結構
#    {
#      'id': str,  # 網站上獨一無二的回應識別號碼，若回應者是保戶則設為None
#      'floor': int,     # 第幾個回應
#      'dateTime': str,  # 發文時間、日期
#      'author': dict,   # 描述作者的一個字典
#      'content': str,   # 內文
#      'belongsTo': int  # 屬於哪篇文章，這個數字會與所屬文章的 id 相同
#    }
#
# user:
#  - 描述
#    描述使用者的一個字典，每個鍵值為相對應的欄位
#  - 結構
#    {
#      'userName': str,  # 用戶在網站上使用的暱稱
#      'sex': str,       # 'male' 或 'female'，若保戶則 None （無法取得）
#      'identity': str,  # 'insurer'（保戶）或 'salesman'（業務員）
#      'region': str     # 業務員的服務區域，若為保戶則設為 None
#    }
import sys


if '-h' in sys.argv or '--help' in sys.argv:
    print(sys.modules[__name__].__doc__)
    sys.exit()


from bs4 import BeautifulSoup

import bs4
import json
import requests
import time


'''
==========================================================================
Subprograms
==========================================================================
'''

def parse_content(contents):  # contents: list of div tags
    result = []
    for para in contents:
        # post contents may contains one or more div tags
        lines = [i for i in para.children]

        for i in range(len(lines)):
            if lines[i].name == 'br':
                lines[i] = bs4.element.NavigableString('\n')
            elif lines[i].name == 'a':
                if lines[i].next.name == 'img':  # this is an image tag
                    lines[i] = bs4.element.NavigableString(
                                f'\n<img>{lines[i].next["src"]}<img>\n'
                                )
                else:  # this is a simple link anchor
                    lines[i] = lines[i].text
            elif isinstance(lines[i], bs4.element.Tag):  # other tag
                name = lines[i].name
                lines[i] = bs4.element.NavigableString(
                        f'<{name}>{lines[i].next}<{name}>'
                        )

            lines[i].replace(u'\xa0', u' ').strip()

        result += lines

    return ''.join(result)


def add_user(soup, db, identity):
    user = {}
    author_name = soup.find('span', class_='font-weight-bold').get_text()
    user['userName'] = author_name
    user['identity'] = identity
    db['users'].append(user)


def get_post(index):
    response = requests.get(URL_BASE + '/' + str(index))
    sp=BeautifulSoup(response.text, "html.parser")

    title=sp.find('h1',class_='mb-16-px display-2 display-1-sm')
    content=sp.find('div',class_='post-content')
    comment=sp.find_all('div',class_='comment-content')

    return sp, title, content, comment


def parse_post(soup, database, content, comment):
    # build article author
    # Article author are all insurer, and to protect personal data,
    # insurer have no other infomation beside first two latters
    # of username
    add_user(soup, database, 'insurer')

    # build article
    article = {}
    article['id'] = n
    article['title'] = title.get_text(strip=True)
    cls_time = soup.find('div', class_='t6 text-gray-1')
    # NOTE: "．" (i.e. chr(65294)) is not a dot (".")
    article['class'] = cls_time.get_text(strip=True).split('．')[0]
    article['dateTime'] = cls_time.get_text(strip=True).split('．')[1]
    article['author'] = database['users'][-1]
    article['content'] = parse_content(content.find_all('div'))

    # build replies
    meta_comments = soup.find_all(
            'div',
            class_='d-flex justify-content-start mb-24-px'
            )[1:]  # the first one is for article
    replies = []
    for i in range(len(comment)):  # len(meta_comments) == len(comment)
        reply = {}
        reply['belongsTo'] = n
        reply['content'] = parse_content(comment[i].find_all('div'))
        # parse metadata
        flr_time = meta_comments[i].find('div', class_='t6 text-gray-1')
        # NOTE: "．" (i.e. chr(65294)) is not a dot (".")
        floor = flr_time.get_text(strip=True).split('．')[0].lstrip('B')
        # because of skipping the deleted comments, we can not simply
        # set i as floor.
        reply['floor'] = int(floor)
        reply['dateTime'] = flr_time.get_text(strip=True).split('．')[1]
        # build author from a comment
        try:
            # TODO: find a way sign-in and keep sign-in
            # Direct consultation could see more infomation of a salesman,
            # but it need to sign-in first...
            # PS. we will need this: requests.Session()
            # https://stackoverflow.com/questions/31554771/how-to-use-cookies-in-python-requests
            url_consultation = meta_comments[i].find('a').get('href')
            salesman = True
        except AttributeError:  # the comment is made by an insurer
            salesman = False
        if salesman:
            add_user(meta_comments[i], database, 'salesman')
            reply_id = url_consultation.split('=')[1]
        else:
            add_user(meta_comments[i], database, 'insurer')
            reply_id = None
        reply['author'] = database['users'][-1]
        reply['id'] = reply_id
        database['replies'].append(reply)
        replies.append(database['replies'][-1])

    article['replies'] = replies
    database['articles'].append(article)


def print_post(title, content, comment, database):
    PRINT_JSON = '-j' in sys.argv or '--json' in sys.argv
    if PRINT_JSON:
        print(json.dumps(database, ensure_ascii=False))
    else:
        print(title.get_text(strip=True))
        print(content.get_text(strip=True))
        print('回應------------------------------------------------------')
        for i in range(len(comment)):
            print('回應',i+1)
            print(comment[i].get_text(strip=True))
            print()

'''
==========================================================================
Main Program - Initializing Data Container
==========================================================================
'''

json_ = {}
json_['articles'] = []
json_['classes'] = ['投保規劃', '保單健檢', '理賠申請',
                    '理賠申請', '保險觀念']
json_['users'] = []
json_['replies'] = []

'''
==========================================================================
Main Program - Interactive Mode
==========================================================================
'''

URL_BASE = "https://finfo.tw/posts"
INTERACTIVE = not ('-i' in sys.argv or '--index' in sys.argv)

while INTERACTIVE:
    n=int(input('請輸入文章號碼:(輸入0則結束)'))
    if n==0:
        break
    soup, title, content, comment = get_post(n)

    if title is None:
        print('文章不存在或已被刪除')
        continue

    parse_post(soup, json_, content, comment)
    print_post(title, content, comment, json_)

'''
==========================================================================
Main Program - Single Post Mode
==========================================================================
'''

if not INTERACTIVE:
    if '-i' in sys.argv:
        _index = sys.argv.index('-i')
    else:
        _index = sys.argv.index('--index')

    try:
        int(sys.argv[_index + 1])
    except ValueError:
        print(f'參數錯誤（-i {sys.argv[_index + 1]}）：文章編號須為正整數')
        sys.exit(1)

    n = str(sys.argv[_index + 1])
    soup, title, content, comment = get_post(n)

    if title is None:
        print('文章不存在或已被刪除')
    else:
        parse_post(soup, json_, content, comment)
        print_post(title, content, comment, json_)

'''
==========================================================================
Main Program - Save Data
==========================================================================
'''

if '-o' in sys.argv or '--output' in sys.argv:
    try:
        path_index = sys.argv.index('-o') + 1
    except ValueError:
        path_index = sys.argv.index('--output') + 1

    OUTPUT_PATH = sys.argv[path_index]
else:
    now = time.strftime('%b%d_%H%M_%Y', time.localtime())
    OUTPUT_PATH = 'finfo_forum_' + now + '.json'

if len(json_['articles'])                \
        and not ('-n' in sys.argv)       \
        and not ('--nosave' in sys.argv):
    with open(OUTPUT_PATH, 'w') as file:
        json.dump(json_, file, indent=4, ensure_ascii=False)
