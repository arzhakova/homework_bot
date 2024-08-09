import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from requests import HTTPError, RequestException
from telebot import apihelper, TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(funcName)s,'
                              ' %(lineno)d] %(message)s')
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения, необходимых для работы."""
    missing_tokens = [name for name in TOKENS if not globals()[name]]
    if missing_tokens:
        logger.critical('Отсутствуют токены')
        raise ValueError('Отсутствуют токены')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    logger.debug('Начало отправки сообщения')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug(f'Бот отправил сообщение:"{message}"')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    logger.debug('Начало запроса к эндпоинту API сервиса Практикум Домашка')
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
    except RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API сервиса Практикум '
                              f'Домашка с параметром {payload}: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise HTTPError(f'Код ответа API сервиса Практикум Домашка '
                        f'с параметром {payload}: '
                        f'{homework_statuses.status_code}')
    logger.debug('Получение ответа API сервиса Практикум Домашка '
                 'прошло успешно')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API."""
    logger.debug('Начало проверки ответа API сервиса Практикум Домашка')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API сервиса Практикум Домашка является не '
                        f'словарем, а {type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Отсутствие ключа "homeworks" в ответе API '
                       'сервиса Практикум Домашка')
    if not isinstance(response['homeworks'], list):
        raise TypeError(f'Данные о домашних работах в ответе API сервиса '
                        f'Практикум Домашка являются не списком, а '
                        f'{type(response["homeworks"])}')
    logger.debug('Проверка ответа API сервиса Практикум Домашка прошла '
                 'успешно')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logger.debug('Начало извлечения статуса домашней работы из ответа API '
                 'сервиса Практикум Домашка')
    if 'status' not in homework:
        raise KeyError('Отсутствие статуса домашней работы в ответе API '
                       'сервиса Практикум Домашка')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствие названия домашней работы в ответе API '
                       'сервиса Практикум Домашка')
    homework_status = homework['status']
    homework_name = homework['homework_name']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неожиданный статус домашней работы: '
                         f'{homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.debug('Извлечение статуса домашней работы из API сервиса Практикум '
                 'Домашка прошла успешно')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    bot_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response['homeworks']
            if not homework:
                logger.debug('Обновлений статуса домашней работы не найдено')
                continue
            homework_message = parse_status(homework[0])
            if homework_message != bot_message:
                send_message(bot, homework_message)
                bot_message = homework_message
                timestamp = response.get('current_date') or int(time.time())
        except apihelper.ApiException as error:
            logger.exception(f'Ошибка телеграмма: {error}')
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.exception(error_message)
            if error_message != bot_message:
                with suppress(apihelper.ApiException):
                    send_message(bot, error_message)
                    bot_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
