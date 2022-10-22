import json
import re
import settings
from dispatcher import FINAL_DATE
from datetime import datetime, time, timedelta

from generate_ticket import generate_ticket

CITIES_PATTERN = r'(МОСКВ)|(ЛОНД)|(ПАРИ)|(НЬЮ)|(ПЕКИ)|(БЕРЛ)|(СЕУЛ)|(ТОК)|(ОТТАВ)|(КАНБЕ)'
DATE_PATTERN = r'\d{2}-\d{2}-\d{4}'

"""

Handler - функция, принимающая на вход text (текст сообщения) и context (словарь с данными). Возвращает bool.
True - если шаг пройден, False - если данные введены неверно.

"""


def handle_departure_city(text, context):
    city_match = re.match(CITIES_PATTERN, text.upper())
    if city_match:
        context['departure_city'] = [city for city in settings.FLIGHT_TIMETABLE if city.startswith(city_match[0])][0]
        return True
    else:
        return False


def handle_destination_city(text, context):
    city_match = re.match(CITIES_PATTERN, text.upper())
    if city_match:
        for city in settings.FLIGHT_TIMETABLE[context['departure_city']]:
            if city.startswith(city_match[0]):
                context['destination_city'] = city
                return True
        else:
            context['want_break'] = True
            return True
    else:
        context['want_break'] = True
        return True


def handle_ask_date(text, context):
    date_match = re.match(DATE_PATTERN, text)
    context['dates_to_choose'] = find_flight_dates(date=date_match[0], context=context)
    if context['dates_to_choose']:
        context['_dates_list'] = '\n'.join([f'{i + 1}. {date}' for (i, date) in enumerate(context['dates_to_choose'])])
        return True
    else:
        return False


def find_flight_dates(date, context):
    """
    Алгоритм для поиска 5 дат вылета, ближайших к заданной пользователем.
    Информация о полетах берется из flights.json.
    Если дата, указанная пользователем, находится позднее, чем через 2 года, пользователю будет отправлено сообщение
    о невозможности забронировать билеты на эту дату.
    Если дата, указанная пользователем, находится в прошлом, ищет даты вылета, начиная с сегодняшнего дня.
    :param date: дата вылета, указанная пользователем
    :param context: контекст с атрибутами для каждого пользователя
    :return: Возвращает 5 дат, ближайших к указанной пользователем
    """
    try:
        user_flight_date = datetime.strptime(date, '%d-%m-%Y')
    except ValueError:
        return False

    today = datetime.now()
    actual_timedelta = FINAL_DATE - user_flight_date
    if user_flight_date < today:
        user_flight_date = today
    elif actual_timedelta < timedelta(days=178):
        context['alternative_failure_text'] = True
        return False

    picked_flight_time = settings.FLIGHT_TIMETABLE[context['departure_city']][context['destination_city']]['time']
    flight_time = time.fromisoformat(picked_flight_time)
    user_flight_date = datetime.replace(user_flight_date, hour=flight_time.hour, minute=flight_time.minute)

    with open('flights.json', mode='r', encoding='utf8') as file:
        flights_timetable = json.load(file)
    picked_flight_info = flights_timetable[context['departure_city']][context['destination_city']]

    for i, date in enumerate(picked_flight_info):
        parsed_date = datetime.strptime(date, '%d-%m-%Y %H:%M')
        if user_flight_date > parsed_date:
            continue
        else:
            dates_to_choose = picked_flight_info[i: i + 5]
            break

    return dates_to_choose


def handle_chosen_date(text, context):
    try:
        context['flight_datetime'] = context['dates_to_choose'][int(text) - 1]
        striped_string = context['flight_datetime'].partition('  ')
        context['flight_date'] = striped_string[0]
        context['flight_time'] = striped_string[2]
        return True
    except IndexError:
        return False


def handle_name(text, context):
    context['name'] = text
    return True


def handle_passengers_amount(text, context):
    if 1 <= int(text) <= 5:
        context['passengers_amount'] = int(text)
        return True
    else:
        return False


def handle_email(text, context):
    context['email'] = text
    return True


def handle_comment(text, context):
    context['comment'] = text
    return True


def handle_feedback(text, context):
    if text.lower() == 'да':
        return True
    elif text.lower() == 'нет':
        context['want_break'] = True
        return True
    else:
        return False


def handle_phone_number(text, context):
    context['phone_number'] = text
    return True


def handle_ticket(text, context):
    return generate_ticket(context)
