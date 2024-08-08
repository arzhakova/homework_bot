import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from http import HTTPStatus
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения, необходимых для работы."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение:"{message}"')
    except Exception as error:
        raise Exception(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if homework_statuses.status_code == HTTPStatus.OK:
            return homework_statuses.json()
        else:
            raise Exception(f'Код ответа API: {homework_statuses.status_code}')
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверяет ответ API."""
    try:
        response['homeworks'] and response['current_date']
    except KeyError:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    try:
        homework = response['homeworks']
        if isinstance(homework, list):
            return homework[0]
        else:
            raise TypeError('Данные приходят не в виде списка')
    except IndexError:
        raise IndexError('Список работ пуст')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework['status'] and homework['homework_name']
    except KeyError:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    homework_status = homework['status']
    homework_name = homework['homework_name']
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        raise KeyError('Неожиданный статус домашней работы')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют токены')
        sys.exit()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    homework_status_message = ''
    error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            message = parse_status(check_response(response))
            if message != homework_status_message:
                send_message(bot, message)
                homework_status_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
