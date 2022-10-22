from PIL import Image, ImageDraw, ImageFont
from libgravatar import Gravatar
import requests
import os.path
from io import BytesIO

SOURCE_PATH = os.path.dirname(__file__)
RELATIVE_TEMPLATE_PATH = "files/ticket-base.jpg"
TEMPLATE_PATH = os.path.normpath(os.path.join(SOURCE_PATH, RELATIVE_TEMPLATE_PATH))
FONT_RELATIVE_PATH = "files/Roboto-Regular.ttf"
FONT_PATH = os.path.normpath(os.path.join(SOURCE_PATH, FONT_RELATIVE_PATH))
FONT_SIZE = 20
BLACK = (0, 0, 0, 255)

NAME_OFFSET = (45, 273)
FLIGHT_DATE_OFFSET = (45, 123)
FLIGHT_TIME_OFFSET = (205, 123)
DEPARTURE_CITY_OFFSET = (45, 175)
DESTINATION_CITY_OFFSET = (45, 225)

AVATAR_SIZE = 90
AVATAR_OFFSET = (490, 160)


def generate_ticket(context):
    base = Image.open(TEMPLATE_PATH).convert("RGBA")
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    draw = ImageDraw.Draw(base)
    draw.text(NAME_OFFSET, context['name'], font=font, fill=BLACK)
    draw.text(FLIGHT_DATE_OFFSET, context['flight_date'], font=font, fill=BLACK)
    draw.text(FLIGHT_TIME_OFFSET, context['flight_time'], font=font, fill=BLACK)
    draw.text(DEPARTURE_CITY_OFFSET, context['departure_city'], font=font, fill=BLACK)
    draw.text(DESTINATION_CITY_OFFSET, context['destination_city'], font=font, fill=BLACK)

    avatar = Gravatar(email=context['email'])

    response = requests.get(url=avatar.get_image(size=AVATAR_SIZE, default='robohash'))
    avatar_file_like = BytesIO(response.content)
    avatar = Image.open(avatar_file_like)

    base.paste(avatar, box=AVATAR_OFFSET)

    temp_file = BytesIO()
    base.save(temp_file, format='png')
    temp_file.seek(0)

    return temp_file

