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
    width = len(pic[0])
    return (width, height)

def div_round_up(v, x):
    r = v / x
    ir = int(r)
    if r > ir:
        ir += 1
    return ir

def draw(pic, crop_width = None, crop_height = None):
    (width, height) = get_size(pic)
    if crop_height:
        height = crop_height
    if crop_width:
        width = crop_width

    pic_s = make_2d(div_round_up(width, 2), div_round_up(height, 4), braille_char_offset)

    for y in range(0, height):
        line = pic[y]
        for x in range(0, width):
            pixel = line[x]
            pix = pixel_map[y % 4][x % 2]
            if pixel:
                pic_s[int(y / 4)][int(x / 2)] |= pix
            else:
                pic_s[int(y / 4)][int(x / 2)] &= ~pix

    cout = ""
    for line in pic_s:
        out = ""
        for pixel in line:
            out += "{}".format(chr(pixel))
        cout += out + "\n"
    return cout

def set_pixel(pic, x, y, value=True):
    (width, height) = get_size(pic)

    if x >= 0 and y >= 0 and x < width and y < height:
        pic[y][x] = value

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
usage.add_argument("--time-cutoff", default="2:00:00", help="time at which to cut off the graph")
#usage.add_argument('squeueargs', nargs=argparse.REMAINDER, help="arguments to be passed to squeue")
(args, extra_args) = usage.parse_known_args()

#print(extra_args)

import shutil
dim = shutil.get_terminal_size((80, 20))
term_width  = dim.columns
term_height = dim.lines

print("Terminal dimensions: {} x {}".format(term_width, term_height))

stdout = subprocess.run(["squeue", "--format", "%i;%u;%T;%M;%R"] + extra_args, stdout=subprocess.PIPE, encoding="utf-8").stdout
data = parse(stdout)

min_time = parse_time_to_seconds("00:00")
max_time = parse_time_to_seconds(args.time_cutoff)

def draw_slurm_chart(data, x=0, y=0, width=None, height=None):
    d_width = (width or 80)*2
    time_scale = (1 / max_time) * d_width

    dpic = make_pic(d_width, len(data))
    y = 0
    for e in data:
        if e["STATE"] != "RUNNING":
            continue
        t = e["TIME"]
        r = parse_time_to_seconds(t)

        r = max(min_time, r)
        r = min(max_time, r)

        for i in range(0, int(r * time_scale)):
            set_pixel(dpic, i, y)
        y += 1
        #print(r)
    print(draw(dpic, crop_height=y))

draw_slurm_chart(data, width=term_width)
print("{} jobs drawn".format(y-1))

