#!/usr/bin/env python3
"""
ship-cinema — ocean-cinema denizinde yuzen gemiler.

Bu proje ocean-cinema'nin Gerstner deniz motorunu IMPORT eder: gemi, deniz
yuzeyini 3 noktadan (pruva/orta/kic) ornekleyerek heave + pitch yapar.

    python3 gemi.py --scene scenes/kargo_sakin.json
"""

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ocean-cinema"))

from ocean import Deniz, png_yaz  # noqa: E402


# ---------------------------------------------------------------- gemi cizimi

def gemi_ciz(img, cx, su_y, boy, yuk, yatis, govde_renk, üst_renk, baca_renk,
             isi_izi=None):
    """Yan gorunum gemi silueti. cx = merkez x, su_y = su hatti, yatis = radyan."""
    H, W = img.shape[:2]
    L = boy / 2

    # govde polygonu (pruva kivrigi + kic)
    govde = [
        (-L, -yuk * 0.35), (-L * 0.86, -yuk * 0.08), (-L * 0.5, yuk * 0.06),
        (L * 0.55, yuk * 0.1), (L * 0.86, -yuk * 0.02), (L, -yuk * 0.42),
        (L * 0.88, -yuk * 0.55), (-L * 0.82, -yuk * 0.55), (-L, -yuk * 0.35),
    ]

    def donük_nokta(px, py):
        dx, dy = px, py - yuk * 0.1
        rx = dx * math.cos(yatis) - dy * math.sin(yatis)
        ry = dx * math.sin(yatis) + dy * math.cos(yatis)
        return int(cx + rx), int(su_y + ry)

    for i in range(len(govde) - 1):
        x0, y0 = donük_nokta(*govde[i])
        x1, y1 = donük_nokta(*govde[i + 1])
        cizgi_kalin(img, x0, y0, x1, y1, govde_renk, 4)

    # dolgu: govde polygonunu tarayarak doldur (scanline)
    ys = [donük_nokta(*g)[1] for g in govde]
    xs = [donük_nokta(*g)[0] for g in govde]
    y_min, y_maks = int(max(0, min(ys))), int(min(H, max(ys)) + 1)
    for yy in range(y_min, y_maks + 1):
        kes = []
        n = len(govde)
        for i in range(n):
            x0, y0 = donük_nokta(*govde[i])
            x1, y1 = donük_nokta(*govde[(i + 1) % n])
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                t = (yy - y0) / (y1 - y0)
                kes.append(x0 + (x1 - x0) * t)
        kes.sort()
        for a, b in zip(kes[::2], kes[1::2]):
            xi0, xi1 = int(a), int(b)
            if xi1 > xi0:
                img[yy, xi0:xi1] = govde_renk

    # üst yapı (köprü üstü blokları)
    bloklar = [
        (-L * 0.1, -yuk * 1.15, L * 0.34, yuk * 0.75),
        (L * 0.28, -yuk * 0.85, L * 0.2, yuk * 0.5),
    ]
    for (bx, by, bw, bh) in bloklar:
        x0, y0 = donük_nokta(bx, by)
        x1, y1 = donük_nokta(bx + bw, by - bh)
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        img[max(0, y0):y1, max(0, x0):x1] = üst_renk

    # baca + duman izi (statik; duman animasyonu karelerde gorsel katmanda)
    baca_x, baca_y = donük_nokta(L * 0.15, -yuk * 1.3)
    img[max(0, baca_y - 26):baca_y, baca_x - 6:baca_x + 8] = baca_renk

    # direk + bayrak
    direk_x, direk_y0 = donük_nokta(L * 0.42, -yuk * 1.25)
    direk_y1 = donük_nokta(L * 0.42, -yuk * 2.1)[1]
    cizgi_kalin(img, direk_x, direk_y1, direk_x, direk_y0, (40, 40, 48), 2)
    img[direk_y1:direk_y1 + 14, direk_x + 2:direk_x + 16] = (200, 40, 40)


def cizgi_kalin(img, x0, y0, x1, y1, renk, kalinlik=1):
    adim = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
    for i in range(adim + 1):
        t = i / adim
        x, y = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
        if kalinlik == 1:
            if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
                img[y, x] = renk
        else:
            y0b, y1b = y - kalinlik // 2, y + kalinlik // 2 + 1
            x0b, x1b = x - kalinlik // 2, x + kalinlik // 2 + 1
            img[max(0, y0b):y1b, max(0, x0b):x1b] = renk
