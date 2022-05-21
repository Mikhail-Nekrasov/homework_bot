import logging
import os
import requests
import telegram
import time
from dotenv import load_dotenv
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from settings import ENDPOINT, HOMEWORK_STATUSES, RETRY_TIME


load_dotenv()

logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log', maxBytes=50000000, backupCount=5
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}  # Данную константу
# оставил здесь, т.к. если ее перенести в settings - возникает ошибка из-за
# цикличности импорта: ImportError: cannot import name 'ENDPOINT' from
# partially initialized module 'settings' (most likely due to a circular
# import)


def send_message(bot, message):
    """Функция отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(message)
    except telegram.error.TelegramError as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Получение ответа от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except Exception:
        message = 'Сбой при запросе к ENDPOINT'
        logging.error(message)
    if homework_statuses.status_code == HTTPStatus.OK:
        return homework_statuses.json()
    elif homework_statuses.status_code != HTTPStatus.OK:
        message = 'ENDPOINT недоступен'
        logging.error(message)
        raise AssertionError(message)


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) is dict:
        if 'homeworks' in response:
            if type(response['homeworks']) is not list:
                message = 'Ответ от API с ключом "homeworks" не в виде списка'
                logging.error(message)
                raise TypeError(message)
            return response['homeworks']
        else:
            message = 'В ответе API отсутствет ожидаемый ключ "homeworks"'
            logging.error(message)
            raise AssertionError(message)

    else:
        message = 'Ответ API имеет некорректный формат'
        logging.error(message)
        raise TypeError(message)


def parse_status(homework):
    """Извлечение статуса и подготовка строки для отправки в чат."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        message = 'Недокументированный статус домашней работы в ответе API'
        logger.error(message)
        raise KeyError(message)


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if check_tokens():
        current_timestamp = int(time.time())
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        status = ''
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homework = check_response(response)
                if homework:
                    if homework[0] != status:
                        status = parse_status(homework[0])
                        send_message(bot, status)
                else:
                    logger.debug(
                        'Новый статус домашней работы отсутствует'
                    )

                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                time.sleep(RETRY_TIME)

    else:
        message = 'Отсутствуют обязательные переменные окружения'
        logger.critical(message)
        return None


if __name__ == '__main__':
    main()
