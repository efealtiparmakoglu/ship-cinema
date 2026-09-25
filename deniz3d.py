#!/usr/bin/env python3
"""ship-cinema 3B — Gerstner dalga alaninda 3B yuzme.

ocean-cinema/ocean_render.py ile AYNI Gerstner formulleri (tek evren):
    faz    = k * (dx*x + dz*y) - omega*t
    z      = A * sin(faz)                      -> dusey yer degistirme
    x,y   += steep * chop * lam/(2pi) * cos(faz) -> yatay (choppiness)

Sahne JSON'u ocean-cinema HD sahneleriyle ayni "ocean" blogunu okur;
"float" blogu gemilerin yerini/basini ve amplitude_scale'i tasiyar.
"""

import json
import math

G = 9.81


def dalgalar_hazirla(oc_cfg):
    """JSON dalga listesini (k, omega, dx, dz, A, steep) sayilarina cevirir."""
    hazir = []
    ham = oc_cfg.get("waves", [])
    for w in ham:
        lam = w["wavelength"]
        k = 2 * math.pi / lam
        omega = math.sqrt(G * k)
        dir_rad = math.radians(w["direction_deg"])
        steep = w.get("steepness", 0.5) / (k * max(1, len(ham)))
        hazir.append({
            "k": k, "omega": omega, "A": w["amplitude"],
            "dx": math.cos(dir_rad), "dz": math.sin(dir_rad),
            "steep": steep * lam / (2 * math.pi),
        })
    return hazir


def yuzey(dalgalar, x, y, t, chop=0.8, amplitude_scale=1.0):
    """(x, y)'de dusey yer degistirme (yuzey yaklasimi, yatay kayma ihmal)."""
    z = 0.0
    for w in dalgalar:
        faz = w["k"] * (w["dx"] * x + w["dz"] * y) - w["omega"] * t
        z += w["A"] * amplitude_scale * math.sin(faz)
    return z


def yuzme_ornekle(dalgalar, px, py, t, boy, genislik, heading_rad,
                  chop=0.8, amplitude_scale=1.0):
    """GemiGovdesi ornekleme: (heave, pitch, roll) radyan dondurur.

    Gemi basi +X lokal; heading z-donmesiyle dunyaya gecer.
    pruva/kic -> pitch, iskele/sancak -> roll.
    """
    hx, sxx = math.cos(heading_rad), math.sin(heading_rad)
    ileri = (hx, sxx)          # bas yonu (dünya)
    yan = (-sxx, hx)           # iskele yonu (dünya)

    p_pruva = (px + ileri[0] * boy * 0.4, py + ileri[1] * boy * 0.4)
    p_kic = (px - ileri[0] * boy * 0.4, py - ileri[1] * boy * 0.4)
    p_sancak = (px + yan[0] * genislik * 0.4, py + yan[1] * genislik * 0.4)
    p_iskele = (px - yan[0] * genislik * 0.4, py - yan[1] * genislik * 0.4)

    h_pruva = yuzey(dalgalar, *p_pruva, t, chop, amplitude_scale)
    h_kic = yuzey(dalgalar, *p_kic, t, chop, amplitude_scale)
    h_sancak = yuzey(dalgalar, *p_sancak, t, chop, amplitude_scale)
    h_iskele = yuzey(dalgalar, *p_iskele, t, chop, amplitude_scale)

    heave = (h_pruva + h_kic + h_sancak + h_iskele) / 4.0
    pitch = -math.atan2(h_pruva - h_kic, boy * 0.8)   # +pitch: pruva kalkar
    roll = math.atan2(h_sancak - h_iskele, genislik * 0.8)
    return heave, pitch, roll


def sahne_yukle(yol):
    cfg = json.load(open(yol, encoding="utf-8"))
    oc = cfg["ocean"]
    return cfg, dalgalar_hazirla(oc), oc.get("choppiness", 0.8), \
        cfg.get("float", {}).get("amplitude_scale", 1.0)
