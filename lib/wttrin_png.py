#!/usr/bin/python
#vim: encoding=utf-8

import sys
import os
import re
import time

"""
This module is used to generate png-files for wttr.in queries.
The only exported function is:

        make_wttr_in_png(filename)

in filename (in the shortname) is coded the weather query.
The function saves the weather report in the file and returns None.
"""

import requests

from PIL import Image, ImageFont, ImageDraw
import pyte.screens

# downloaded from https://gist.github.com/2204527
# described/recommended here:
#
#   http://stackoverflow.com/questions/9868792/find-out-the-unicode-script-of-a-character
#
import unicodedata2

MYDIR = os.path.abspath(os.path.dirname( os.path.dirname('__file__')))
PNG_CACHE = os.path.join(MYDIR, "cache/png")

COLS = 180
ROWS = 100

CHAR_WIDTH = 7
CHAR_HEIGHT = 14

# How to find font for non-standard scripts:
#
# $ fc-list :lang=ja

FONT_SIZE = 12
FONT_CAT = {
    'default':      "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    'Cyrillic':     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    'Greek':        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    'Han':          "/usr/share/fonts/truetype/motoya-l-cedar/MTLc3m.ttf",
    'Hiragana':     "/usr/share/fonts/truetype/motoya-l-cedar/MTLc3m.ttf",
}

def color_mapping(color):
    """
    Convert pyte color to PIL color
    """
    if color == 'default':
        return 'lightgray'
    if color in ['green', 'black', 'cyan', 'blue', 'brown']:
        return color
    try:
        return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
    except:
        # if we do not know this color and it can not be decoded as RGB,
        # print it and return it as it is (will be displayed as black)
        # print color
        return color
    return color

def strip_buf(buf):
    """
    Strips empty spaces from behind and from the right side.
    (from the right side is not yet implemented)
    """
    def empty_line(line):
        "Returns True if the line consists from spaces"
        return all(x.data == ' ' for x in line)

    def line_len(line):
        "Returns len of the line excluding spaces from the right"

        last_pos = len(line)
        while last_pos > 0 and line[last_pos-1].data == ' ':
            last_pos -= 1
        return last_pos

    number_of_lines = 0
    for line in buf[::-1]:
        if not empty_line(line):
            break
        number_of_lines += 1

    buf = buf[:-number_of_lines]

    max_len = max(line_len(x) for x in buf)
    buf = [line[:max_len] for line in buf]

    return buf

def script_category(char):
    """
    Returns category of a Unicode character
    Possible values:
        default, Cyrillic, Greek, Han, Hiragana
    """
    cat = unicodedata2.script_cat(char)[0]
    if char == u'：':
        return 'Han'
    if cat in ['Latin', 'Common']:
        return 'default'
    else:
        return cat

def gen_term(filename, buf):
    buf = strip_buf(buf)
    cols = len(buf[0])
    rows = len(buf)

    image = Image.new('RGB', (cols * CHAR_WIDTH, rows * CHAR_HEIGHT))

    buf = buf[-ROWS:]

    draw = ImageDraw.Draw(image)
    font = {}
    for cat in FONT_CAT:
        font[cat] = ImageFont.truetype(FONT_CAT[cat], FONT_SIZE)

    x_pos = 0
    y_pos = 0
    for line in buf:
        x_pos = 0
        for char in line:
            current_color = color_mapping(char.fg)
            if char.bg != 'default':
                draw.rectangle(
                    ((x_pos, y_pos),
                     (x_pos+CHAR_WIDTH, y_pos+CHAR_HEIGHT)),
                    fill=color_mapping(char.bg))

            cat = script_category(char.data)
            if cat not in font:
                print "Unknown font category: %s" % cat
            draw.text(
                (x_pos, y_pos),
                char.data,
                font=font.get(cat, font.get('default')),
                fill=current_color)
            #sys.stdout.write(c.data)

            x_pos += CHAR_WIDTH
        y_pos += CHAR_HEIGHT
        #sys.stdout.write('\n')

    image.save(filename)

def typescript_to_one_frame(png_file, text):
    """
    Render text (terminal sequence) in png_file
    """

    # fixing some broken characters because of bug #... in pyte 6.0
    text = text.replace('Н', 'H').replace('Ν', 'N')

    screen = pyte.screens.Screen(COLS, ROWS)
    #screen.define_charset("B", "(")

    stream = pyte.streams.ByteStream()
    stream.attach(screen)

    stream.feed(text)

    gen_term(png_file, screen.buffer)

#
# wttr.in related functions
#

def parse_wttrin_png_name(name):
    """
    Parse the PNG filename and return the result as a dictionary.
    For example:
        input = City_200x_lang=ru.png
        output = {
            "lang": "ru",
            "width": "200",
            "filetype": "png",
            "location": "City"
        }
    """

    parsed = {}

    if name.lower()[-4:] == '.png':
        parsed['filetype'] = 'png'
        name = name[:-4]

    parts = name.split('_')
    parsed['location'] = parts[0]

    for part in parts:
        if re.match('(?:[0-9]+)x', part):
            parsed['width'] = part[:-1]
        elif re.match('x(?:[0-9]+)', part):
            parsed['height'] = part[1:]
        elif re.match(part, '(?:[0-9]+)x(?:[0-9]+)'):
            parsed['width'], parsed['height'] = part.split('x', 1)
        elif '=' in part:
            arg, val = part.split('=', 1)
            parsed[arg] = val

    return parsed

def make_wttrin_query(parsed):
    """
    Convert parsed data into query name
    """

    for key in ['width', 'height', 'filetype']:
        if key in parsed:
            del parsed[key]

    location = parsed['location']
    del parsed['location']

    args = []
    if 'options' in parsed:
        args = [parsed['options']]
        del parsed['options']
    else:
        args = []

    for key, val in parsed.items():
        args.append('%s=%s' % (key, val))

    url = "http://wttr.in/%s" % location
    if args != []:
        url += "?%s" % ("&".join(args))

    return url


def make_wttr_in_png(png_name, options=None):
    """
    The function saves the weather report in the file and returns None.
    The weather query is coded in filename (in the shortname).
    """

    parsed = parse_wttrin_png_name(png_name)

    # if location is MyLocation it should be overriden 
    # with autodetected location (from options)
    if parsed.get('location', 'MyLocation') == 'MyLocation':
        del parsed['location']

    if options is not None:
        for key, val in options.items():
            if key not in parsed:
                parsed[key] = val
    url = make_wttrin_query(parsed)

    timestamp = time.strftime("%Y%m%d%H", time.localtime())
    cached_basename = url[14:].replace('/','_')

    cached_png_file = "%s/%s/%s.png" % (PNG_CACHE, timestamp, cached_basename)

    dirname = os.path.dirname(cached_png_file)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if os.path.exists(cached_png_file):
        return cached_png_file

    text = requests.get(url).text.replace('\n', '\r\n')
    curl_output = text.encode('utf-8')

    typescript_to_one_frame(cached_png_file, curl_output)

    return cached_png_file
