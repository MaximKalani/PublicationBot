# -*- coding: utf-8 -*-

import time
import eventlet
import requests
import logging
import telebot
import urllib
from time import sleep
from tokens import BOT_TOKEN, VK_TOKEN

# Каждый раз получаем по 10 последних записей со стены
URL_VK = 'https://api.vk.com/method/wall.get?domain=mhkon&count=10&filter=owner&v=5.73&access_token=' + VK_TOKEN
FILENAME_VK = 'last_known_id.txt'
BASE_POST_URL = 'https://vk.com/wall-'

CHANNEL_NAME = '@omgtest'

# Если True, предполагается использование cron для запуска скрипта
# Если False, процесс запускается и постоянно висит запущенный
SINGLE_RUN = True

bot = telebot.TeleBot(BOT_TOKEN)

def get_data():
    #функция возвращает 10 последних постов
    timeout = eventlet.Timeout(10)
    try:
        feed = requests.get(URL_VK)
        return feed.json()
    except eventlet.timeout.Timeout:
        logging.warning('Got Timeout while retrieving VK JSON data. Cancelling...')
        return None
    finally:
        timeout.cancel()

def send_pic(att):
    #функция скачивает фото и отправляет его сообщением
    logging.info('PHOTO detected')
    url = att['photo']['photo_604']
    f = open('out.jpg','wb')
    f.write(urllib.request.urlopen(url).read())
    f.close()
    img = open('out.jpg', 'rb')
    bot.send_photo(CHANNEL_NAME, img)
    img.close()
        
def send_doc(att):
    #функция скачивает документ и отправляет его сообщением
    logging.info('DOC detected')
    if 'gif' in att['doc']['ext']:
        logging.info('ITS GIF!')
        if att['doc']['size']<=5000000:   
            logging.info('GIF is small enough')
            url = att['doc']['url']
            f = open('out.gif','wb')
            f.write(urllib.request.urlopen(url).read())
            f.close()
            doc = open('out.gif', 'rb')
            bot.send_document(CHANNEL_NAME, doc)
            doc.close()
        else:
            logging.info('GIF is too large, skipping')

def send_new_posts(items, last_id):
    #функция отправляет текст и проверяет посты на наличие вложений
    for item in items:
        if item['id'] <= last_id:
            #если пост уже был обработан ранее - прекратить
            break
        if item['text'] != '':
            #если в посте есть текст, то отправить его + ссылку на оригинальный пост
            link = '{!s}{!s}_{!s}'.format(BASE_POST_URL, str(-item['owner_id']), item['id'])
            bot.send_message(CHANNEL_NAME, item['text']+'\n\nSource: '+ link, disable_web_page_preview=1)

        if 'attachments' in item:
            #если есть вложения - обработать их
            for att in item['attachments']:
                if 'photo' in att:
                    send_pic(att)
                if 'doc' in att:
                    send_doc(att)
                    
                
        # Спим секунду, чтобы избежать разного рода ошибок и ограничений (на всякий случай!)
        time.sleep(1)
    return      

def check_new_posts_vk():
    # Пишем текущее время начала
    logging.info('[VK] Started scanning for new posts')
    with open(FILENAME_VK, 'rt') as file:
        last_id = int(file.read())
        if last_id is None:
            logging.error('Could not read from storage. Skipped iteration.')
            return
        logging.info('Previous last_id is {!s}'.format(last_id))
    try:
        feed = get_data()
        # Если ранее случился таймаут, пропускаем итерацию. Если всё нормально - парсим посты.
        if feed is not None:
            # 0 - это какое-то число, так что начинаем с 1
            entries = feed['response']['items']
            try:
                # Если пост был закреплен, пропускаем его
                tmp = entries[0]['is_pinned']
                send_new_posts(entries[1:], last_id)
            except KeyError:
                send_new_posts(entries, last_id)
            # Записываем новую "верхушку" группы, чтобы не повторяться
            with open(FILENAME_VK, 'wt') as file:
                try:
                    tmp = entries[0]['is_pinned']
                    # Если первый пост - закрепленный, то сохраняем ID второго
                    file.write(str(entries[1]['id']))
                    logging.info('New last_id (VK) is {!s}'.format((entries[1]['id'])))
                except KeyError:
                    file.write(str(entries[0]['id']))
                    logging.info('New last_id (VK) is {!s}'.format((entries[0]['id'])))
    except Exception as ex:
        logging.error('Exception of type {!s} in check_new_post(): {!s}'.format(type(ex).__name__, str(ex)))
        pass
    logging.info('[VK] Finished scanning')
    return


if __name__ == '__main__':
    # Избавляемся от спама в логах от библиотеки requests
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    # Настраиваем наш логгер
    logging.basicConfig(format='[%(asctime)s] %(filename)s:%(lineno)d %(levelname)s - %(message)s', level=logging.INFO,
                        filename='bot_log.log', datefmt='%d.%m.%Y %H:%M:%S')
    if not SINGLE_RUN:
        while True:
            check_new_posts_vk()
            # Пауза в 4 минуты перед повторной проверкой
            logging.info('[App] Script went to sleep.')
            time.sleep(60 * 4)
    else:
        check_new_posts_vk()
    logging.info('[App] Script exited.\n')
