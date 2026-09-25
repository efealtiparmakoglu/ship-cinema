#!/usr/bin/env python3
# Blender icinde: blender --background --python gemi_render.py -- --scene scenes3d/tanker_firtina.json [--gif 36]
"""ship-cinema 3B — gemiler ocean-cinema'nin Cycles denizinde yuzer.

Sahne JSON'u = ocean-cinema HD sahne formati + "ships" + "float" bloklari.
"""

import argparse
import math
import os
import shutil
import subprocess
import sys

import bpy
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
sys.path.insert(0, os.path.join(BURASI, "..", "ocean-cinema"))

import gemi3d  # noqa: E402
import deniz3d  # noqa: E402
import ocean_render as oc  # noqa: E402


# ---------------------------------------------------------------- deniz mesh

def deniz_kur(oc_cfg, dalgalar, chop, olcek, t):
    size = oc_cfg.get("size", 80)
    seg = oc_cfg.get("segments", 512)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=seg, y_subdivisions=seg, size=size)
    obj = bpy.context.active_object
    obj.name = "okyanus"
    temel = np.array([v.co[:] for v in obj.data.vertices])

    mat = bpy.data.materials.new("Okyanus")
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    renk = oc_cfg.get("color", (0.004, 0.025, 0.07))
    b.inputs["Base Color"].default_value = (renk[0], renk[1], renk[2], 1)
    b.inputs["Roughness"].default_value = oc_cfg.get("roughness", 0.055)
    b.inputs["IOR"].default_value = 1.33
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    noise.inputs["Detail"].default_value = 12.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.08
        b.inputs["Subsurface Radius"].default_value = (0.3, 0.6, 1.2)
    obj.data.materials.append(mat)

    deniz_guncelle(obj, temel, dalgalar, chop, olcek, t)
    return obj, temel


def yer_degistir(temel, dalgalar, chop, olcek, t):
    """ocean-cinema Gerstner'i (vektorize) — deniz3d ile ayni fizik."""
    px = np.zeros(len(temel))
    py = np.zeros(len(temel))
    pz = np.zeros(len(temel))
    x = temel[:, 0]
    y = temel[:, 1]
    for w in dalgalar:
        faz = w["k"] * (w["dx"] * x + w["dz"] * y) - w["omega"] * t
        A = w["A"] * olcek
        cos_f = np.cos(faz)
        px += w["steep"] * w["dz"] * cos_f * chop
        py += w["steep"] * w["dx"] * cos_f * chop
        pz += A * np.sin(faz)
    sonuc = temel.copy()
    sonuc[:, 0] = x + px
    sonuc[:, 1] = y + py
    sonuc[:, 2] = pz
    return sonuc


def deniz_guncelle(obj, temel, dalgalar, chop, olcek, t):
    verts = yer_degistir(temel, dalgalar, chop, olcek, t)
    obj.data.vertices.foreach_set("co", verts.ravel())
    obj.data.update()


# ---------------------------------------------------------------- gemiler

def gemileri_kur(cfg):
    gemiler = []
    for s in cfg.get("ships", []):
        kok, boy, genis, draft = gemi3d.gemi_olustur(s)
        gemiler.append({
            "kok": kok, "boy": boy, "genis": genis, "draft": draft,
            "pos": tuple(s.get("pos", (0, 0))),
            "heading": math.radians(s.get("heading_deg", 180)),
        })
    return gemiler


def gemileri_guncelle(gemiler, dalgalar, chop, olcek, t):
    for g in gemiler:
        heave, pitch, roll = deniz3d.yuzme_ornekle(
            dalgalar, g["pos"][0], g["pos"][1], t,
            g["boy"], g["genis"], g["heading"], chop, olcek)
        kok = g["kok"]
        kok.location = (g["pos"][0], g["pos"][1], heave)
        # XYZ euler: R = Rz(heading) @ Ry(pitch) @ Rx(roll)
        kok.rotation_euler = (roll, pitch, g["heading"])
        g["son_ornekleme"] = (round(heave, 3), round(math.degrees(pitch), 2),
                              round(math.degrees(roll), 2))


# ---------------------------------------------------------------- ana

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--gif", type=int, default=0, help="kare sayisi; 0 = tek kare")
    ap.add_argument("--fps", type=int, default=12)
    a = ap.parse_args(args)

    cfg, dalgalar, chop, olcek = deniz3d.sahne_yukle(a.scene)

    if os.environ.get("HIZLI") == "1":
        cfg["render"] = {**cfg.get("render", {}), "width": 800, "height": 450,
                         "samples": 40}
        cfg["output"] = "/tmp/onizleme_gemi_" + os.path.basename(a.scene).replace(".json", ".png")
        print("  [HIZLI] onizleme ->", cfg["output"])
    if a.gif:
        cfg["render"] = {**cfg.get("render", {}), "width": 1280, "height": 720,
                         "samples": 48}

    oc.temiz()
    oc.sahne_kur(cfg)
    oc_cfg = cfg["ocean"]
    deniz, temel = deniz_kur(oc_cfg, dalgalar, chop, olcek, cfg.get("time", 0.0))
    gemiler = gemileri_kur(cfg)

    cam = cfg["camera"]
    oc.kamera_kur(cam["position"], cam["look_at"], cam.get("lens", 40))
    oc.govcem_diski(cfg, cam["position"])

    sc = bpy.context.scene
    out = cfg["output"]
    if a.gif:
        kok_ad = os.path.splitext(out)[0]
        out = kok_ad + ".gif"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    if not a.gif:
        t = cfg.get("time", 0.0)
        deniz_guncelle(deniz, temel, dalgalar, chop, olcek, t)
        gemileri_guncelle(gemiler, dalgalar, chop, olcek, t)
        for g in gemiler:
            print(f"  [gemi] {g['kok'].name} heave/pitch/roll = {g['son_ornekleme']}")
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"== BİTTİ -> {out}")
        return

    # GIF: kare kare deniz + yuzme guncellemesi
    tmp = out + ".frames"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for f in range(a.gif):
        t = f / a.fps
        deniz_guncelle(deniz, temel, dalgalar, chop, olcek, t)
        gemileri_guncelle(gemiler, dalgalar, chop, olcek, t)
        sc.render.filepath = f"{tmp}/f{f:05d}.png"
        bpy.ops.render.render(write_still=True)
        print(f"  kare {f + 1}/{a.gif} t={t:.2f} {gemiler[0]['son_ornekleme']}")

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
                    "-i", f"{tmp}/f%05d.png",
                    "-vf", "palettegen=max_colors=256:stats_mode=diff", f"{tmp}/pal.png"],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
                    "-i", f"{tmp}/f%05d.png", "-i", f"{tmp}/pal.png",
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                    "-loop", "0", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"== BİTTİ -> {out}")


if __name__ == "__main__":
    main()
