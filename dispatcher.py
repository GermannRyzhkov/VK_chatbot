from collections import defaultdict
from datetime import datetime, timedelta, time
import settings
import json

TODAY = datetime.now()
TODAYS_WEEKDAY = TODAY.isoweekday()
FINAL_DATE = datetime.replace(TODAY, year=TODAY.year + 2, month=TODAY.month)
flights_data = defaultdict(dict)


def find_by_weekdays(flight, flight_dates):
    for day in flight['flight_weekdays']:
        if day >= TODAYS_WEEKDAY:
            delta = day - TODAYS_WEEKDAY
        else:
            delta = (7 - TODAYS_WEEKDAY) + day
        flight_date = TODAY + timedelta(days=delta)
        flight_time = time.fromisoformat(flight['time'])
        flight_date_time = datetime.replace(flight_date, hour=flight_time.hour, minute=flight_time.minute)
        flight_dates.append(flight_date_time)

    flight_buffer = sorted(flight_dates)
    i = 0
    while flight_dates[-1] < FINAL_DATE:
        next_flight = flight_buffer[i] + timedelta(days=7)
        flight_dates.append(next_flight)
        flight_buffer[i] = next_flight
        i += 1
        if i == len(flight_buffer):
            i = 0


def find_by_dates(flight, flight_dates):
    for date in flight['flight_dates']:
        if date >= TODAY.day:
            flight_date = TODAY.replace(day=date)
        else:
            flight_date = TODAY.replace(month=(TODAY.month + 1), day=date)
        flight_time = time.fromisoformat(flight['time'])
        flight_date_time = datetime.replace(flight_date, hour=flight_time.hour, minute=flight_time.minute)
        flight_dates.append(flight_date_time)

    flight_buffer = sorted(flight_dates)
    i = 0
    while flight_dates[-1] < FINAL_DATE:
        if flight_buffer[i].month < 12:
            next_flight = flight_buffer[i].replace(month=flight_buffer[i].month + 1)
        else:
            next_flight = flight_buffer[i].replace(year=flight_buffer[i].year + 1, month=1)
        flight_dates.append(next_flight)
        flight_buffer[i] = next_flight
        i += 1
        if i == len(flight_buffer):
            i = 0


def format_flight_dates(flight_dates):
    flight_dates.sort()
    for i, date in enumerate(flight_dates):
        flight_dates[i] = date.strftime('%d-%m-%Y  %H:%M')
    return flight_dates


def run():
    for departure, arrivals in settings.FLIGHT_TIMETABLE.items():
        for arrival in arrivals:
            flight = settings.FLIGHT_TIMETABLE[departure][arrival]
            flight_dates = []
            if flight['flight_weekdays']:
                find_by_weekdays(flight, flight_dates)
            elif flight['flight_dates']:
                find_by_dates(flight, flight_dates)
            flights = format_flight_dates(flight_dates)
            flights_data[departure][arrival] = flights
    with open('flights.json', mode='w', encoding='utf8') as file:
        json.dump(flights_data, file, indent=4, ensure_ascii=False)
