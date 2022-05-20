import logging
import os
import requests
import telegram
import time
from dotenv import load_dotenv
from http import HTTPStatus
from logging.handlers import RotatingFileHandler


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

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
BOT = telegram.Bot(token=TELEGRAM_TOKEN)


def send_message(bot, message):
    """Функция отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(message)
    except Exception as error:
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
        send_message(BOT, message)
    if homework_statuses.status_code == HTTPStatus.OK:
        return homework_statuses.json()
    elif homework_statuses.status_code != HTTPStatus.OK:
        message = 'ENDPOINT недоступен'
        logging.error(message)
        send_message(BOT, message)
        raise AssertionError(message)


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) is dict:
        try:
            if type(response['homeworks']) is not list:
                message = 'Ответ от API с ключом "homeworks" не в виде списка'
                logging.error(message)
                send_message(BOT, message)
                raise TypeError(message)
            return response['homeworks']
        except Exception:
            message = 'В ответе API отсутствет ожидаемый ключ "homeworks"'
            logging.error(message)
            send_message(BOT, message)
            raise AssertionError(message)

    else:
        message = 'Ответ API имеет некорректный формат'
        logging.error(message)
        send_message(BOT, message)
        raise TypeError(message)


def parse_status(homework):
    """Извлечение статуса и подготовка строки для отправки в чат."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        message = 'Недокументированный статус домашней работы в ответе API'
        logger.error(message)
        send_message(BOT, message)
        raise KeyError(message)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if None in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        message = 'Отсутствуют обязательные переменные окружения'
        logger.critical(message)
        send_message(BOT, message)
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time())
    status = ''
    if check_tokens():
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homework = check_response(response)
                if homework:
                    if homework[0] != status:
                        status = parse_status(homework[0])
                        send_message(BOT, status)
                else:
                    logger.debug(
                        'Новый статус домашней работы отсутствует'
                    )

                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(BOT, message)
                time.sleep(RETRY_TIME)

    else:
        return None


if __name__ == '__main__':
    main()
