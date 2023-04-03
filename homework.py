"""Telegram-бот, который обращается к API сервиса Практикум.Домашка."""

import logging
import os
import requests
import telegram
import time

from dotenv import load_dotenv


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
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    env_list = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    err_list = []
    for var_name in env_list:
        if not globals()[var_name]:
            err_list.append(var_name)
    if err_list:
        logger.critical(
            f'Отсутствуют обязательные переменные окружения - {err_list}. '
            'Программа принудительно остановлена.'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение \'{message}\' отправлено в чат.')
    except telegram.TelegramError as error:
        logger.error(f'Сбой при отправке сообщения в Telegram - {error}.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if homework_statuses.status_code != 200:
            raise ConnectionError('Эндпойнт недоступен.')
        try:
            return homework_statuses.json()
        except requests.exceptions.JSONDecodeError as error:
            raise requests.exceptions.JSONDecodeError(
                f'Ошибка json-конвертации - {error}.'
            )
    except requests.RequestException:
        raise ConnectionError('Эндпойнт недоступен.')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответствует типу данных.')
    if 'homeworks' not in response:
        raise KeyError('В API ответе отсутствует ключ \'homeworks\'.')
    if 'current_date' not in response:
        raise KeyError('В API ответе отсутствует ключ \'current_date\'.')
    response_hw = response['homeworks']
    if not isinstance(response_hw, list):
        raise TypeError('Ответ API не является списком.')
    return response_hw


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    if not isinstance(homework, dict):
        raise TypeError('\'homework\' не соответствует типу данных.')

    hw_keys = ['homework_name', 'status']

    for key in hw_keys:
        if not homework.get(key):
            raise KeyError(f'Отсутствует ключ \'{key}\' в ответе API.')

    hw_status = homework['status']
    if hw_status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(
            f'Неожиданный статус \'{hw_status}\' домашней работы.'
        )

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[hw_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)  # type: ignore
    one_month = 2629743
    timestamp = int(time.time()) - one_month

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(response['homeworks'][0])
                send_message(bot, message)
                timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
