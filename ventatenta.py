import time
import datetime
import os
import sys
import logging

import http.cookiejar
import http.client
from urllib.request import urlopen, build_opener, install_opener, HTTPCookieProcessor
from urllib.parse import urlencode
from bs4 import BeautifulSoup

import smtplib # email

import multiprocessing

PORTALEN = 'https://www3.student.liu.se'
URL_LOGIN = 'https://www3.student.liu.se/portal/login'

cj = http.cookiejar.CookieJar()
opener = build_opener(HTTPCookieProcessor(cj))
opener.addheaders = [('User-agent', 'Mozilla/5.0')]
install_opener(opener)

# Pushover app ventatenta
APP_TOKEN = 'a2isjzsxfcjt3q7qsh8mfc3xpmxfdy'

# Wait 10 minutes
SLEEP_TIME = 600

# Shared variable for multiprocessing thingy, bad solution
LOGIN_RESULT = ''

# Logging
LOG_FILENAME = 'ventatenta.log'
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Times to poll between
TIME_START = datetime.time(7, 30)
TIME_END = datetime.time(18, 0)

# Login credentials
if len(sys.argv) >= 2:
    try:
        user = __import__(sys.argv[1].replace('.py', ''))
        LOGIN_NAME = user.name
        LOGIN_DATA = user.data
        MAIL = user.mail
        USER_KEY = user.push_key

    except Exception as e:
        print(e)
        print('Import error, filename: {}'.format(sys.argv[1]))
else:
    print('create login file')
    sys.exit(1)

login_data = urlencode(LOGIN_DATA).encode('ascii')

# Print + logging to file
def s_print(msg):
    print(msg)
    logging.debug(msg)

def send_email(text):
    print('Trying to send mail')
    mail = 'potatis-potatis@hotmail.com'
    pw = 'potatisbragrejer1337'
    target = MAIL

    if len(target) == 0:
        print('Bad email')
        return

    FROM = mail
    TO = [target]
    SUBJECT = 'Tentaresultat'
    TEXT = 'Resultat: \n {}'.format(text)

    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)

    print(message)
    try:
        server = smtplib.SMTP('smtp.live.com', 587)
        server.ehlo()
        server.starttls()
        server.login(mail, pw)
        server.sendmail(mail, target, message)
        server.close()
    except Exception as e:
        print('Failed to send mail')
        print(e)

# Push notification to pushover user
def push(msg='No text', url=URL_LOGIN):
    if len(USER_KEY) == 0:
        print('no push')
        return
    s_print('Trying to push...')
    try:
        conn = http.client.HTTPSConnection('api.pushover.net:443')
        conn.request('POST', '/1/messages.json',
          urlencode({
            'token': APP_TOKEN,
            'user': USER_KEY,
            'message': msg,
            'url': url,
            'url_title': 'Studieresultat',
          }), { 'Content-type': 'application/x-www-form-urlencoded' })
        conn.getresponse()
    except Exception as e:
        s_print('Failed to push')
        s_print(e)

# Either push notificationor email
def notify_user(msg):
    if USER_KEY != '':
        push(msg) # Pushover
    if MAIL != '':
        send_email(msg) # Email

# Login to portalen and get URL to studieresultat, stored in global LOGIN_RESULT because didn't solve it nice
def get_url():
    s_print('Logging in')
    global LOGIN_RESULT
    LOGIN_RESULT = ''
    try:
        resp = urlopen(URL_LOGIN, login_data)
        soup = BeautifulSoup(resp.read(), 'html.parser')

        for font in soup.find_all('font', text=True):
            if font.text.lstrip() == 'Studieresultat':
                LOGIN_RESULT = PORTALEN + font.parent['href']
                s_print(LOGIN_RESULT)
                s_print('Login Success')
                break
        else:
            s_print('Login Fail')
    except Exception as e:
        s_print('Get URL failed')
        s_print(e)

# Parse page for results
def ventatenta(url_resultat):
    s_print('URL:' + url_resultat)
    result = []
    resp = urlopen(url_resultat)
    soup = BeautifulSoup(resp.read(), 'html.parser')

    try:
        content = soup.find('table', {'class': 'resultlist'})
    except:
        s_print('no content found...')
        s_print(soup)
        return result

    if not content:
        s_print('no resultlist found...')
        s_print('content')
        s_print(content)
        s_print('soup')
        s_print(soup)
        return result

    try:
        hej = content.find_all('tr')
    except:
        s_print('no trs found')
        s_print(content)
        return result

    for tr in content.find_all('tr'):
        links = tr.find('a')
        if not links:
            b = tr.find('b')
            tds = tr.find_all('td')
            if not b:
                if len(tds) == 5:
                    code, name, hp, grade, date = tds
                    result.append([code.text, name.text, hp.text, grade.text, date.text])

    return result

# INIT
get_url()
url_resultat = LOGIN_RESULT
prev_result = ventatenta(url_resultat)
s_print('STARTUP')
s_print(LOGIN_NAME)
notify_user('Startup {0}, {1} \n kurser: {2}'.format(time.strftime('%X'), LOGIN_NAME, len(prev_result)))

pushed_today = False
while True:
    now = datetime.datetime.now().time()
    s_print(LOGIN_NAME)
    s_print('Now: {}'.format(time.strftime('%c')))

    # During the day
    TIME_START = datetime.time(7, 30)
    TIME_END = datetime.time(7, 45)
    if TIME_START <= now <= TIME_END:
        notify_user('Snurrar fortfarande. Antal kurser: {}'.format(len(prev_result)))

    if True:
        # multiprocessing to catch timeout in logging in
        login = multiprocessing.Process(target=get_url)
        login.start()
        # Wait 10 seconds or until process finishes
        login.join(10)
        # If still lives, kill it
        if login.is_alive():
            print('Login timed out :(')
            login.terminate()
            login.join()
            continue
        else:
            print('login worked')

        # Page stored in LOGIN_RESULT
        if len(LOGIN_RESULT) == 0:
            s_print('len of login == 0')
            continue

        # Parse out results from page
        try:
            result = ventatenta(LOGIN_RESULT)
            s_print('Nr of courses: ' + str(len(result)))
            points = 0
            # Iterate through all course results
            for row in result:
                # New result!
                if not row in prev_result:
                    msg = ' '.join(row)
                    s_print(msg)
                    notify_user(msg)
                points += float(row[2])

            s_print('POINTS: ' + str(points))
            s_print(time.strftime('%c'))

            prev_result = result[:]
        except Exception as e:
            s_print('Parsing of page failed')
            s_print(e)
            print(e)

    for i in range(SLEEP_TIME):
        print('\033[KSleeping for {} seconds'.format(SLEEP_TIME-i), end='\r')
        time.sleep(1)
    print('\033[K')
