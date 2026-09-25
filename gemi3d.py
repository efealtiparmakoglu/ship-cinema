#!/usr/bin/env python3
"""ship-cinema 3B — prosedürel gemi gövdeleri (Blender içinden).

İki tip: konteyner gemisi ve tanker. Gövde: X boyunca 26 istasyonda
kapalı kesitlerin loft'u (kaburgalar), su hattı altı kırmızı antifouling,
güverte gri; köprü üst yapısı, baca, direk, konteyner/boru güverte yuku.

Gemi yerel +X = pruva, origin = su hattı (keel z = -draft).
"""

import math
import random

import bpy

# ---------------------------------------------------------------- yardımcılar

MAT_CACHE = {}


def mat_yap(ad, renk, rough=0.5, metalik=0.0):
    if ad in MAT_CACHE:
        return MAT_CACHE[ad]
    m = bpy.data.materials.new(ad)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (renk[0], renk[1], renk[2], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metalik
    MAT_CACHE[ad] = m
    return m


def kutu(ad, merkez, boyut, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=merkez)
    o = bpy.context.active_object
    o.name = ad
    o.scale = boyut  # size=1 kubun kenari 1: scale = tam boyut
    o.data.materials.append(mat)
    return o


def silindir(ad, merkez, r, yukseklik, mat, eksen="Z"):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=yukseklik,
                                        location=merkez, vertices=24)
    o = context_obj(ad)
    if eksen == "X":
        o.rotation_euler = (0, math.pi / 2, 0)
    elif eksen == "Y":
        o.rotation_euler = (math.pi / 2, 0, 0)
    o.data.materials.append(mat)
    return o


def context_obj(ad):
    o = bpy.context.active_object
    o.name = ad
    return o


# ---------------------------------------------------------------- gövde loft

PROFIL = [(0.50, 0.00), (0.50, -0.42), (0.44, -0.72),
          (0.30, -0.92), (0.12, -1.00), (0.00, -1.02)]


def govde_loft(boy, genis, draft, serbest=2.6, istasyon=26):
    """Kapalı kesitleri X boyunca loft'lar. (verts, faces, mat_index) döner.

    mat_index: 0=hava tarafı, 1=su altı (kırmızı), 2=güverte.
    """
    keel0 = -draft
    halkalar = []
    deck_cift = []

    for i in range(istasyon):
        t = i / (istasyon - 1)
        x = -boy / 2 + boy * (t ** 0.85)
        u = 2 * x / boy  # ~[-L/B .. L/B] normalized

        # genişlik: orta gövde platosu, pruvada inel, kıçta transom
        if u > 1.2:
            q = (u - 1.2) / (boy / genis - 1.2)
            w = genis * max(0.015, (1 - q ** 1.9) ** 0.55)
        elif u < -1.2:
            q = (-u - 1.2) / (boy / genis - 1.2)
            w = genis * (0.70 + 0.30 * q)
        else:
            w = genis

        zdeck = serbest + 0.8 * max(0.0, u) ** 2 + 0.22 * max(0.0, -u) ** 2
        zkeel = keel0 + draft * (0.42 * max(0.0, u) ** 2.2 + 0.30 * max(0.0, -u) ** 2)
        derinlik = zdeck - zkeel
        # pruva rake'i: üst kesitler öne kayar
        bow_w = max(0.0, u - 0.6) / (boy / genis - 0.6) if u > 0.6 else 0.0
        rake = 1.3 * bow_w

        halka = []
        for (yf, zf) in PROFIL:
            z = zdeck + zf * derinlik
            xn = x + rake * (1.0 + zf) * 0.5  # üstte tam rake, keelde yarı
            halka.append((xn, -yf * w / 2, z))          # iskele: güverte -> omurga
        for idx in range(len(PROFIL) - 2, -1, -1):       # sancak: omurga -> güverte
            (yf, zf) = PROFIL[idx]
            z = zdeck + zf * derinlik
            xn = x + rake * (1.0 + zf) * 0.5
            halka.append((xn, yf * w / 2, z))
        halkalar.append(halka)
        deck_cift.append((halka[0], halka[-1]))          # iskele/sancak güverte kenarı

    verts = []
    for h in halkalar:
        verts.extend(h)
    n = len(PROFIL) * 2 - 1  # halka nokta sayısı (omurga teki, güverte uçları açık)

    faces = []
    mat_of_face = []
    for i in range(len(halkalar) - 1):
        for j in range(n - 1):  # güverte kenarları arası açıklık güverte şeridine kalır
            j2 = j + 1
            faces.append((i * n + j, i * n + j2, (i + 1) * n + j2, (i + 1) * n + j))

    # güverte: iskele-sancak kenar çizgileri arası şerit
    deck_start = len(verts)
    for (p, q) in deck_cift:
        verts.append(p)
        verts.append(q)
    for i in range(len(halkalar) - 1):
        a = deck_start + 2 * i
        faces.append((a, a + 2, a + 3, a + 1))
        mat_of_face.append(2)

    # kıç transom kapağı: son istasyon halkası tek çokgen (normali kıça baksın)
    faces.append(tuple(range(len(halkalar) * n - 1, (len(halkalar) - 1) * n - 1, -1)))
    mat_of_face.append(0)

    return verts, faces, mat_of_face


def govde_kur(ad, boy, genis, draft, mat_hava, mat_su, mat_gunte):
    verts, faces, mat_of_face = govde_loft(boy, genis, draft)
    mesh = bpy.data.meshes.new(ad)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for p in mesh.polygons:
        p.use_smooth = True
    for m in (mat_hava, mat_su, mat_gunte):
        mesh.materials.append(m)
    # su altı: dünya z=0'ın altı kırmızı (gemi origin su hattında)
    for p, mi in zip(mesh.polygons, mat_of_face):
        if mi == 2:
            p.material_index = 2
            continue
        zs = [mesh.vertices[v].co.z for v in p.vertices]
        p.material_index = 1 if (sum(zs) / len(zs)) < 0.0 else 0
    bpy.ops.object.select_all(action="DESELECT")
    obj = bpy.data.objects.new(ad, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- üst yapı

def zdeck_nokta(boy, x, serbest=2.6):
    """Güverte yüksekliği x'te — govde_loft ile ayni sheer formülü."""
    u = 2 * x / boy
    return serbest + 0.8 * max(0.0, u) ** 2 + 0.22 * max(0.0, -u) ** 2


def ust_yapi(kok, boy, genis, govde_mat, renkler):
    ust_renk = renkler.get("ust", (0.88, 0.88, 0.9))
    ust = mat_yap("Ustyapi", ust_renk, rough=0.42)
    cam = mat_yap("KopruCam", (0.02, 0.03, 0.04), rough=0.15)
    x0 = -boy * 0.36
    zd = zdeck_nokta(boy, x0)
    zdk = zdeck_nokta(boy, x0 - boy * 0.09)

    kutu("anaBlok", (x0, 0, zd + 1.45), (boy * 0.17, genis * 0.62, 2.9), ust)
    kutu("kopru", (x0 + boy * 0.02, 0, zd + 3.5), (boy * 0.13, genis * 0.68, 1.2), ust)
    kutu("camBandi", (x0 + boy * 0.02, 0, zd + 3.5),
         (boy * 0.132, genis * 0.70, 0.42), cam)
    kutu("kicHali", (x0 - boy * 0.09, 0, zdk + 0.6),
         (boy * 0.06, genis * 0.5, 1.2), ust)

    silindir("baca", (x0 - boy * 0.075, 0, zd + 2.8), genis * 0.09, 2.2,
             mat_yap("Baca", renkler.get("baca", (0.75, 0.2, 0.12)), rough=0.5))
    silindir("bacaUcu", (x0 - boy * 0.075, 0, zd + 3.95), genis * 0.095, 0.25,
             mat_yap("BacaSiyah", (0.015, 0.015, 0.015), rough=0.6))
    silindir("direk", (x0 + boy * 0.09, 0, zd + 4.7), 0.055, 2.8,
             mat_yap("Metal", (0.75, 0.76, 0.78), rough=0.35, metalik=0.8))
    silindir("direkKolu", (x0 + boy * 0.09, 0, zd + 5.5), 0.04, 1.5,
             MAT_CACHE["Metal"], eksen="Y")

    # filika (turuncu kapsül)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45,
                                         location=(x0 + boy * 0.03, genis * 0.40, zd + 1.0),
                                         segments=16, ring_count=10)
    filika = context_obj("Filika")
    filika.scale = (1.6, 1.0, 1.0)
    filika.data.materials.append(mat_yap("Filika", (0.85, 0.35, 0.05), rough=0.5))


# ---------------------------------------------------------------- yükler

KONT_RENK = [(0.72, 0.16, 0.08), (0.10, 0.38, 0.62), (0.78, 0.58, 0.10),
             (0.15, 0.45, 0.25), (0.55, 0.55, 0.58), (0.45, 0.12, 0.30)]


def konteyner_yuku(kok, boy, genis):
    rng = random.Random(7)
    bay_w = boy * 0.085
    n_bay = int((boy * 0.52) / bay_w)
    x0 = -boy * 0.16
    for bay in range(n_bay):
        x = x0 + bay * bay_w
        zd = zdeck_nokta(boy, x)
        for kat in range(2):
            for sira in range(4):
                y = -genis * 0.36 + sira * genis * 0.24
                renk = KONT_RENK[rng.randrange(len(KONT_RENK))]
                m = mat_yap(f"Kont{renk}", renk, rough=0.6)
                kutu(f"kont{bay}_{kat}_{sira}",
                     (x, y, zd + 0.42 + kat * 0.86),
                     (bay_w * 0.86, genis * 0.225, 0.82), m)


def tanker_yuku(kok, boy, genis):
    m_boru = mat_yap("Boru", (0.32, 0.28, 0.24), rough=0.5, metalik=0.5)
    m_ayak = mat_yap("Catwalk", (0.28, 0.29, 0.31), rough=0.6)
    zd0 = zdeck_nokta(boy, 0)
    silindir("anaBoru", (0, 0, zd0 + 0.26), 0.13, boy * 0.84,
             m_boru, eksen="X")
    kutu("catwalk", (0, 0, zd0 + 0.48), (boy * 0.82, 0.55, 0.07), m_ayak)
    for i, xf in enumerate((-0.38, -0.19, 0.0, 0.19, 0.38)):
        kutu(f"catwalkAyak{i}", (boy * xf, 0, zd0 + 0.28), (0.1, 0.1, 0.42), m_ayak)
    for i, xf in enumerate((-0.30, -0.02, 0.26)):
        x = boy * xf
        zd = zdeck_nokta(boy, x)
        silindir(f"manifold{i}", (x, 0, zd + 0.30), 0.14, genis * 0.70,
                 m_boru, eksen="Y")
        for ys in (-1, 1):
            kutu(f"vanalar{i}_{ys}", (x, ys * genis * 0.32, zd + 0.34),
                 (0.5, 0.4, 0.4), mat_yap("Vana", (0.45, 0.22, 0.08), rough=0.5))


# ---------------------------------------------------------------- tipler

def _ship_olustur(ad, tip, boy, genis, draft, renkler):
    random.seed(3)
    MAT_CACHE.clear()
    govde_renk = renkler.get("govde", (0.015, 0.04, 0.10))
    m_hava = mat_yap("Gövde", govde_renk, rough=0.5)
    m_su = mat_yap("Antifouling", renkler.get("su_alti", (0.45, 0.08, 0.05)), rough=0.55)
    m_gunte = mat_yap("Gunte", (0.30, 0.31, 0.33), rough=0.65)
    MAT_CACHE["Gunte"] = m_gunte

    kok = bpy.data.objects.new(ad, None)
    bpy.context.collection.objects.link(kok)
    once = set(bpy.data.objects)

    govde = govde_kur(f"{ad}_govde", boy, genis, draft, m_hava, m_su, m_gunte)

    ust_yapi(kok, boy, genis, m_hava, renkler)
    if tip == "konteyner":
        konteyner_yuku(kok, boy, genis)
    else:
        tanker_yuku(kok, boy, genis)

    # kurulum sirasinda yaratilan TUM parçalar kok'e baglanir (pozisyon/rotasyon
    # gemiyle birlikte tasinsin)
    for o in set(bpy.data.objects) - once:
        if o is not kok:
            o.parent = kok
    return kok


def gemi_olustur(cfg):
    """Scene JSON'daki 'ships' girdisinden gemi kurar. (kok, boy, genis, draft)"""
    s = cfg
    tip = s.get("tip", "konteyner")
    boy = s.get("boy", 28.0)
    genis = s.get("genis", boy / 4.0)
    draft = s.get("draft", boy / 15.5)
    renkler = s.get("renkler", {})
    kok = _ship_olustur(s.get("ad", tip), tip, boy, genis, draft, renkler)
    return kok, boy, genis, draft
