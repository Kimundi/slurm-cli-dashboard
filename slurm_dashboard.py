#!/usr/bin/env python3

import re
import subprocess
import sys
import argparse

################################################################################
# braille drawing
################################################################################

pixel_map = ((0x01, 0x08),
             (0x02, 0x10),
             (0x04, 0x20),
             (0x40, 0x80))

# braille unicode characters starts at 0x2800
braille_char_offset = 0x2800

def make_2d(width, height, value):
    return [[value] * width for i in range(height)]

def make_pic(width, height):
    pic = make_2d(width, height, False)
    return pic

def get_size(pic):
    height = len(pic)
    width = 0
    if height > 0:
        width = len(pic[0])
    return (width, height)

def div_round_up(v, x):
    r = v / x
    ir = int(r)
    if r > ir:
        ir += 1
    return ir

def draw_mono_braille(pic, out_pic, xoffset=0, yoffset=0):
    (width, height) = get_size(pic)

    s_width = div_round_up(width, 2)
    s_height = div_round_up(height, 4)
    pic_s = make_2d(s_width, s_height, braille_char_offset)

    for y in range(0, height):
        for x in range(0, width):
            pixel = pic[y][x]
            pix = pixel_map[y % 4][x % 2]
            if pixel:
                pic_s[int(y / 4)][int(x / 2)] |= pix
            else:
                pic_s[int(y / 4)][int(x / 2)] &= ~pix

    (out_width, out_height) = get_size(out_pic)
    for y in range(0, s_height):
        for x in range(0, s_width):
            target_x = x + xoffset
            target_y = y + yoffset
            set_pixel(out_pic, target_x, target_y, chr(pic_s[y][x]))

def set_pixel(pic, x, y, value):
    (width, height) = get_size(pic)

    if x >= 0 and y >= 0 and x < width and y < height:
        pic[y][x] = value

def get_pixel(pic, x, y):
    (width, height) = get_size(pic)

    if x >= 0 and y >= 0 and x < width and y < height:
        return pic[y][x]
    else:
        return None

def print_canvas(canvas):
    for line in canvas:
        out = ""
        for pixel in line:
            out += pixel
        print(out)

def draw_slurm_chart(data, canvas, xoffset=0, yoffset=0, width=None, height=None, max_time=None):
    (cwidth, cheight) = get_size(canvas)

    d_width = (width or cwidth)*2

    if max_time == None:
        max_time = 0
        for e in data:
            t = e["TIME"]
            r = parse_time_to_seconds(t)
            max_time = max(max_time, r)

    if max_time == 0:
        max_time = 1

    time_scale = (1 / max_time) * d_width

    dpic = make_pic(d_width, len(data))
    y = 0
    for e in data:
        t = e["TIME"]
        r = parse_time_to_seconds(t)

        r = max(min_time, r)
        r = min(max_time, r)

        for i in range(0, int(r * time_scale)):
            set_pixel(dpic, i, y, True)
        y += 1
        #print(r)
    draw_mono_braille(dpic, canvas, xoffset=xoffset, yoffset=yoffset)
    return (div_round_up(y, 4), max_time)

def draw_rectangle(canvas, xoffset=0, yoffset=0, width=None, height=None):
    (cwidth, cheight) = get_size(canvas)
    width = width or cwidth
    height = height or cheight

    def combine(canvas, x, y, sym):
        set_pixel(canvas, x, y, sym)

    for x in range(xoffset + 1, xoffset + width - 1):
        combine(canvas, x,                   yoffset,              '─')
        combine(canvas, x,                   yoffset + height - 1, '─')
    for y in range(yoffset + 1, yoffset + height - 1):
        combine(canvas, xoffset,             y,                    '│')
        combine(canvas, xoffset + width - 1, y,                    '│')

    combine(canvas,     xoffset,             yoffset,              '┌')
    combine(canvas,     xoffset + width - 1, yoffset,              '┐')
    combine(canvas,     xoffset,             yoffset + height - 1, '└')
    combine(canvas,     xoffset + width - 1, yoffset + height - 1, '┘')

def draw_text(canvas, text, xoffset=0, yoffset=0):
    for i in range(0, len(text)):
        set_pixel(canvas, xoffset + i, yoffset, text[i])

################################################################################
# squeue parsing
################################################################################

t_re = re.compile("(([0-9]+)-)?(([0-9]+):)?([0-9]+):([0-9]+)")

def parse(sq_out):
    queue_jobs = []
    lines = list(sq_out.splitlines())
    headings = list(lines[0].split(";"))
    #print(headings)
    for line in lines[1:]:
        row = list(line.split(";"))
        queue_jobs.append({})
        for (key, value) in zip(headings, row):
            queue_jobs[-1][key] = value
    #print(queue_jobs)
    return queue_jobs

def parse_time(s):
    r = t_re.match(s)
    days = r.group(2) or '0'
    hours = r.group(4) or '0'
    mins = r.group(5) or '0'
    secs = r.group(6) or '0'
    return (int(days), int(hours), int(mins), int(secs))

def parse_time_to_seconds(s):
    (days, hours, mins, secs) = parse_time(s)
    return days * 24 * 60 * 60 + hours * 60 * 60 + mins * 60 + secs

################################################################################
# main
################################################################################

usage = argparse.ArgumentParser()
usage.add_argument("--time-cutoff", default="auto", help="time to which to scale the graph before a cutoff. 'auto' for automatic scaling")
#usage.add_argument('squeueargs', nargs=argparse.REMAINDER, help="arguments to be passed to squeue")
(args, extra_args) = usage.parse_known_args()

#print(extra_args)

import shutil
dim = shutil.get_terminal_size((80, 20))
term_width  = dim.columns
term_height = dim.lines

canvas = make_2d(term_width, term_height, " ")

# print("Terminal dimensions: {} x {}".format(term_width, term_height))

data = []

try:
    stdout = subprocess.run(["squeue", "--format", "%i;%u;%T;%M;%R"] + extra_args, stdout=subprocess.PIPE, encoding="utf-8").stdout
    data = parse(stdout)
except:
    pass

min_time = parse_time_to_seconds("00:00")
if args.time_cutoff == "auto":
    max_time = None
else:
    max_time = parse_time_to_seconds(args.time_cutoff)

filtered_data = []
for e in data:
    if e["STATE"] != "RUNNING":
        continue
    filtered_data.append(e)

(h, actual_max_time) = draw_slurm_chart(filtered_data, canvas, max_time=max_time, width=term_width - 2, xoffset=1, yoffset=1)
draw_rectangle(canvas, height = h + 2)
draw_text(canvas, "{}/{} jobs currently running".format(len(filtered_data), len(data)), yoffset=h + 2)
max_time_text = "{:02}:{:02}:{:02}".format(int(actual_max_time / 60 / 60), int(actual_max_time / 60) % 60, int(actual_max_time) % 60)
draw_text(canvas, max_time_text, yoffset=h + 2, xoffset=term_width-len(max_time_text))

print_canvas(canvas)
