#!/usr/bin/env python3
"""
ship-cinema — ocean-cinema denizinde yuzen gemiler.

ocean-cinema'nin Gerstner motorunu import eder; gemi deniz yuzeyini pruva/
orta/kic noktalarindan ornekleyip heave + pitch yapar; dalgalar gemiyi tasir.

    python3 gemi.py --scene scenes/kargo_sakin.json
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ocean-cinema"))

from ocean import Deniz, png_yaz


# ---------------------------------------------------------------- gemi cizimi

def gemi_ciz(img, cx, su_y, boy, yuk, yatis_rad, renkler, detay=True):
    """Yan gorunum gemi silueti; yatis radyan ile govde doner."""
    H, W = img.shape[:2]
    L = boy / 2
    govde = [
        (-L, -yuk * 0.32), (-L * 0.85, -yuk * 0.05), (-L * 0.45, yuk * 0.08),
        (L * 0.55, yuk * 0.12), (L * 0.88, yuk * 0.02), (L, -yuk * 0.4),
        (L * 0.85, -yuk * 0.52), (-L * 0.8, -yuk * 0.52),
    ]

    ca, sa = math.cos(yatis_rad), math.sin(yatis_rad)

    def don(px, py):
        dx, dy = px, py
        return int(cx + dx * ca - dy * sa), int(su_y + dx * sa + dy * ca)

    # govde dolgu (scanline)
    kenar = [don(*p) for p in govde]
    y_min = max(0, min(y for _, y in kenar))
    y_maks = min(H - 1, max(y for _, y in kenar))
    for yy in range(y_min, y_maks + 1):
        kes = []
        n = len(govde)
        for i in range(n):
            x0, y0 = kenar[i]
            x1, y1 = kenar[(i + 1) % n]
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                t = (yy - y0) / (y1 - y0 + 1e-9)
                kes.append(x0 + (x1 - x0) * t)
        kes.sort()
        for k0, k1 in zip(kes[::2], kes[1::2]):
            img[yy, max(0, int(k0)):max(0, int(k1))] = renkler["govde"]

    # kiic supaurstrüktür
    for (bx, by, bw, bh, renk) in [
        (-L * 0.95, -yuk * 1.5, L * 0.4, yuk * 0.9, renkler["üst"]),
        (-L * 0.3, -yuk * 1.1, L * 0.25, yuk * 0.55, renkler["üst2"]),
    ]:
        x0, y0 = don(bx, by)
        x1, y1 = don(bx + bw, by - bh)
        img[max(0, min(y0, y1)):max(y0, y1), max(0, min(x0, x1)):max(x0, x1)] = renk

    # baca
    bx0, by0 = don(-L * 0.12, -yuk * 1.1)
    bx1, by1 = don(-L * 0.02, -yuk * 1.9)
    img[min(by0, by1):max(by0, by1), min(bx0, bx1):max(bx0, bx1)] = renkler["baca"]

    # konteynerler (kargo ise)
    if renkler.get("konteynerler"):
        kont_renkler = [(0.8, 0.2, 0.1), (0.1, 0.5, 0.8), (0.85, 0.65, 0.1), (0.2, 0.6, 0.3)]
        cr = renkler["konteynerler"]
        for row, ky in enumerate((-yuk * 0.5, -yuk * 1.0, -yuk * 1.5)):
            for ci in range(6):
                kx = -L * 0.75 + ci * (L * 1.35 / 6)
                p00 = don(kx, ky)
                p11 = don(kx + L * 0.16, ky - yuk * 0.16)
                renk = tuple(int(c * 255) for c in kont_renkler[(ci + row) % 4])
                y0, y1 = sorted((p00[1], p11[1]))
                x0, x1 = sorted((p00[0], p11[0]))
                if 0 <= y0 and y1 < H:
                    img[y0:y1, max(0, x0):min(W, x1)] = renk
    return


# ---------------------------------------------------------------- sahne kosucu

def kos(cfg):
    sim = cfg["sim"]
    deniz = Deniz(sim["dalgalar"])
    W, H = sim.get("width", 960), sim.get("height", 540)
    fps = sim.get("fps", 20)
    adet = sim.get("frames", 150)
    out = cfg["output"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out + ".frames"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    gemiler = cfg["ships"]
    p = cfg["palette"]

    for f in range(adet):
        t = f / fps
        img = np.zeros((H, W, 3), dtype=np.uint8)
        # gokyuzu
        ust = np.array(p["sky_top"])
        alt = np.array(p["sky_bottom"])
        for y in range(H):
            fr = min(1.0, y / H)
            img[y] = ust * (1 - fr) + alt * fr
        # deniz yuzey profili (tam genislik, geminin bulundugu deniz bolgesinde)
        xler = np.linspace(0, sim.get("view_span", 120), W)
        yuz = deniz.yukseklik(xler, t) * sim.get("amplitud_px", 6)
        su_izin = int(H * 0.55)
        yuzey = su_izin + yuz.astype(int)
        # deniz dolgusu: yuzeyden asagi
        for x in range(W):
            img[yuzey[x]:, x] = p["deniz"]
        # dalga cizgisi
        for x in range(W):
            img[yuzey[x], x] = p.get("yuzey_cizgi", (200, 210, 220))

        # gemileri ciz: su yuzeyini ornekleyip heave + pitch belirle
        for g in gemiler:
            gx = int(W * g["x"]) % W
            boy, yuk = g["boy"], g["yuk"]
            x_orn = np.clip(gx + np.linspace(-boy // 2, boy // 2, 7).astype(int), 0, W - 1)
            su_yuz = yuzey[x_orn]
            heave = int(np.mean(su_yuz)) + g.get("draft", 6)
            pitch = math.atan2(su_yuz[-1] - su_yuz[0], boy)
            gemi_ciz(img, gx, heave, boy, yuk, pitch,
                     g["renkler"], g.get("detay", True))

        png_yaz(f"{tmp}/f{f:05d}.png", img)
        if f % 40 == 0:
            print(f"  kare {f}/{adet}")

    fps_k = fps
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps_k),
                    "-i", f"{tmp}/f%05d.png",
                    "-vf", "palettegen=max_colors=256:stats_mode=diff", f"{tmp}/pal.png"],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps_k),
                    "-i", f"{tmp}/f%05d.png", "-i", f"{tmp}/pal.png",
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                    "-loop", "0", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"== BİTTİ -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.scene, encoding="utf-8"))
    kos(cfg)
