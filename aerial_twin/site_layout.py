"""Parametric reconstruction of the plant aerial view.

Everything is one flat list of primitive dicts so both the pure-python GLB
builder and the Blender script can consume the exact same layout.  Coordinates
are metres, Z-up, origin at the centre of the walled site, +Y towards the top
of the reference render (the forested ridge) and +X to the right.

The dimensions are read off the reference image using the ~24 m wide main road
at the bottom as the scale anchor, so the whole campus lands at roughly
340 x 280 m.  Tune the constants in SITE / the element blocks below to tighten
the match against the reference.
"""

import math
import random

# --- site envelope ----------------------------------------------------------

SITE_W = 340.0          # east-west extent of the walled campus
SITE_D = 280.0          # north-south extent
PAD_Z = 0.0             # finished floor level of the site platform
GROUND = 1400.0         # forest / terrain extent around the site

# --- materials (base_color RGBA, metallic, roughness) -----------------------

MATERIALS = {
    "forest":      ((0.043, 0.086, 0.043, 1.0), 0.0, 0.95),
    "grass":       ((0.180, 0.290, 0.130, 1.0), 0.0, 0.90),
    "lawn":        ((0.220, 0.380, 0.160, 1.0), 0.0, 0.85),
    "pad":         ((0.700, 0.710, 0.720, 1.0), 0.0, 0.80),
    "asphalt":     ((0.140, 0.150, 0.165, 1.0), 0.0, 0.70),
    "paint":       ((0.900, 0.910, 0.920, 1.0), 0.0, 0.55),
    "white_panel": ((0.880, 0.900, 0.925, 1.0), 0.0, 0.45),
    "beige_wall":  ((0.760, 0.755, 0.735, 1.0), 0.0, 0.60),
    "grey_wall":   ((0.560, 0.585, 0.620, 1.0), 0.0, 0.55),
    "dark_wall":   ((0.230, 0.255, 0.300, 1.0), 0.0, 0.50),
    "blue_roof":   ((0.400, 0.520, 0.680, 1.0), 0.10, 0.35),
    "glass":       ((0.320, 0.430, 0.540, 1.0), 0.20, 0.15),
    "metal":       ((0.720, 0.745, 0.780, 1.0), 0.85, 0.30),
    "tank":        ((0.470, 0.560, 0.680, 1.0), 0.35, 0.35),
    "silo":        ((0.860, 0.875, 0.890, 1.0), 0.30, 0.35),
    "trunk":       ((0.130, 0.110, 0.085, 1.0), 0.0, 0.90),
    "conifer":     ((0.070, 0.150, 0.075, 1.0), 0.0, 0.90),
    "hedge":       ((0.110, 0.210, 0.105, 1.0), 0.0, 0.90),
}


def _b(name, mat, pos, size, rot=0.0):
    return {"type": "box", "name": name, "mat": mat, "pos": pos, "size": size, "rot": rot}


def _c(name, mat, pos, radius, height, seg=24):
    return {"type": "cyl", "name": name, "mat": mat, "pos": pos,
            "radius": radius, "height": height, "seg": seg}


# --- terrain, platform, ground cover ---------------------------------------

def terrain():
    p = [
        _b("forest_floor", "forest", (0, 0, -3.0), (GROUND, GROUND, 3.0)),
        _b("site_pad", "pad", (0, 0, PAD_Z - 0.6), (SITE_W, SITE_D, 0.6)),
        # verge of mown grass between the wall and the tree line
        _b("verge", "grass", (0, 0, PAD_Z - 0.9), (SITE_W + 44, SITE_D + 44, 0.4)),
        # the big lawn / sports field on the west side of the campus
        _b("lawn", "lawn", (-96, 34, PAD_Z + 0.02), (86, 52, 0.08)),
        _b("lawn_2", "lawn", (-116, -6, PAD_Z + 0.02), (46, 26, 0.08)),
    ]
    return p


def roads():
    p = [
        # perimeter ring road inside the wall
        _b("ring_n", "asphalt", (0, 124, PAD_Z + 0.04), (SITE_W - 16, 11, 0.1)),
        _b("ring_s", "asphalt", (0, -122, PAD_Z + 0.04), (SITE_W - 16, 11, 0.1)),
        _b("ring_w", "asphalt", (-158, 0, PAD_Z + 0.04), (11, SITE_D - 16, 0.1)),
        _b("ring_e", "asphalt", (158, 0, PAD_Z + 0.04), (11, SITE_D - 16, 0.1)),
        # internal spine roads
        _b("spine_ew", "asphalt", (0, -52, PAD_Z + 0.04), (SITE_W - 40, 13, 0.1)),
        _b("spine_ns", "asphalt", (-58, 20, PAD_Z + 0.04), (12, 190, 0.1)),
        _b("spine_ns2", "asphalt", (96, -10, PAD_Z + 0.04), (12, 150, 0.1)),
        # public road outside the site, bottom of frame, with a junction
        _b("main_road", "asphalt", (-40, -196, PAD_Z - 1.4), (900, 26, 0.2)),
        _b("branch_road", "asphalt", (-232, -60, PAD_Z - 1.4), (24, 300, 0.2)),
        _b("gate_road", "asphalt", (-40, -168, PAD_Z - 1.2), (16, 60, 0.2)),
        # parking apron in the south-west corner
        _b("parking", "asphalt", (-118, -84, PAD_Z + 0.04), (74, 46, 0.1)),
    ]
    # lane markings on the public road
    for i in range(-16, 17):
        p.append(_b(f"lane_{i}", "paint", (-40 + i * 26, -196, PAD_Z - 1.15), (11, 0.7, 0.06)))
    # crosswalk at the gate junction
    for i in range(9):
        p.append(_b(f"zebra_{i}", "paint", (-72 + i * 2.6, -196, PAD_Z - 1.15), (1.3, 22, 0.06)))
    # parking bay stripes
    for i in range(15):
        p.append(_b(f"bay_{i}", "paint", (-152 + i * 5.0, -84, PAD_Z + 0.11), (0.35, 44, 0.05)))
    return p


# --- buildings --------------------------------------------------------------

def buildings():
    p = []

    # A. long slab block along the northern edge (office / dormitory wing)
    p += [
        _b("A_slab", "beige_wall", (-42, 96, PAD_Z), (156, 26, 17.5)),
        _b("A_plinth", "grey_wall", (-42, 96, PAD_Z), (160, 30, 4.5)),
        _b("A_core", "white_panel", (34, 100, PAD_Z), (26, 24, 23.0)),
    ]
    # ribbon glazing on the long façades
    for f in (1, 2, 3):
        z = PAD_Z + 4.5 + (f - 1) * 4.3
        p.append(_b(f"A_glz_s{f}", "glass", (-42, 83.2, z), (150, 0.6, 2.6)))
        p.append(_b(f"A_glz_n{f}", "glass", (-42, 108.8, z), (150, 0.6, 2.6)))
    # roof monitors (the sawtooth strip visible on the slab roof)
    for i in range(17):
        p.append({"type": "gable", "name": f"A_saw{i}", "mat": "metal",
                  "pos": (-114 + i * 9.0, 96, PAD_Z + 17.5), "size": (7.0, 22.0, 2.6),
                  "rot": 0.0})

    # B. tall production hall, north-east
    p += [
        _b("B_hall", "white_panel", (78, 78, PAD_Z), (62, 58, 31.0)),
        _b("B_parapet", "grey_wall", (78, 78, PAD_Z + 31.0), (63, 59, 1.6)),
        _b("B_annex", "grey_wall", (78, 44, PAD_Z), (62, 14, 12.0)),
    ]
    for i in range(4):
        p.append(_b(f"B_rib{i}", "grey_wall", (78, 49.4 + i * 0.0, PAD_Z), (1.2, 59, 31.4)))
    for i, x in enumerate((56, 70, 84, 98)):
        p.append(_b(f"B_fin{i}", "grey_wall", (x, 48.9, PAD_Z), (1.4, 0.8, 31.4)))

    # C. central tower with the vertical-fin façade (the tallest volume)
    p += [
        _b("C_tower", "white_panel", (16, 22, PAD_Z), (36, 34, 44.0)),
        _b("C_cap", "grey_wall", (16, 22, PAD_Z + 44.0), (38, 36, 2.2)),
        _b("C_skirt", "grey_wall", (16, 22, PAD_Z), (46, 42, 9.0)),
    ]
    for i in range(13):  # vertical fins on the south face
        p.append(_b(f"C_fin{i}", "grey_wall", (-1.0 + i * 2.8, 4.9, PAD_Z + 9.0),
                    (0.8, 0.7, 35.0)))

    # D. blue standing-seam hall, west of the tower
    p += [
        _b("D_hall", "white_panel", (-40, 26, PAD_Z), (60, 54, 22.0)),
        _b("D_roof", "blue_roof", (-40, 26, PAD_Z + 22.0), (61, 55, 1.0)),
        _b("D_dock", "grey_wall", (-40, -4, PAD_Z), (60, 8, 7.0)),
    ]
    for i in range(10):  # seam / skylight ribs across the blue roof
        p.append(_b(f"D_seam{i}", "metal", (-40, 2.0 + i * 5.4, PAD_Z + 23.0), (58, 1.1, 0.5)))

    # E. mid-rise block south of the tower
    p += [
        _b("E_block", "white_panel", (-24, -26, PAD_Z), (66, 32, 18.0)),
        _b("E_roof", "blue_roof", (-24, -26, PAD_Z + 18.0), (67, 33, 0.9)),
    ]
    for f in (1, 2, 3):
        p.append(_b(f"E_glz{f}", "glass", (-24, -42.3, PAD_Z + 3.0 + (f - 1) * 4.6),
                    (62, 0.6, 2.4)))

    # F. small west office pavilion
    p += [
        _b("F_office", "grey_wall", (-140, 46, PAD_Z), (32, 24, 13.0)),
        _b("F_roof", "dark_wall", (-140, 46, PAD_Z + 13.0), (33, 25, 0.8)),
    ]

    # G. low blue-roofed workshop strip, west-centre
    p += [
        _b("G_shop", "white_panel", (-104, -22, PAD_Z), (50, 28, 11.0)),
        _b("G_roof", "blue_roof", (-104, -22, PAD_Z + 11.0), (51, 29, 0.8)),
    ]

    # H. south row of low utility / MEP buildings
    for i, x in enumerate((-76, -34, 8, 50, 92)):
        p.append(_b(f"H_util{i}", "grey_wall", (x, -84, PAD_Z), (30, 20, 8.5)))
        p.append(_b(f"H_roof{i}", "blue_roof", (x, -84, PAD_Z + 8.5), (31, 21, 0.7)))

    # I. gatehouse and weighbridge at the south entrance
    p += [
        _b("I_gate", "white_panel", (-40, -122, PAD_Z), (12, 8, 5.0)),
        _b("I_canopy", "metal", (-40, -122, PAD_Z + 5.0), (22, 14, 0.6)),
    ]
    return p


def process_equipment():
    """Tank farm, silos, stacks and the open switchyard."""
    p = []
    # two large process tanks with a banded skirt, east of the hall
    for i, (x, y) in enumerate(((128, 66), (128, 34))):
        p.append(_c(f"tank{i}", "tank", (x, y, PAD_Z), 11.0, 21.0, seg=32))
        p.append(_c(f"tank{i}_top", "metal", (x, y, PAD_Z + 21.0), 11.2, 1.2, seg=32))
        p.append(_c(f"tank{i}_band", "metal", (x, y, PAD_Z + 10.0), 11.3, 0.8, seg=32))
        p.append(_b(f"tank{i}_bund", "grey_wall", (x, y, PAD_Z), (30, 30, 1.6)))
    # slim white silos beside them
    for i, (x, y) in enumerate(((104, 62), (104, 44))):
        p.append(_c(f"silo{i}", "silo", (x, y, PAD_Z), 5.0, 26.0, seg=24))
        p.append({"type": "cone", "name": f"silo{i}_cap", "mat": "metal",
                  "pos": (x, y, PAD_Z + 26.0), "radius": 5.2, "height": 3.0, "seg": 24})
    # exhaust stack behind the production hall
    p.append(_c("stack", "silo", (116, 100, PAD_Z), 2.6, 42.0, seg=20))
    # switchyard / transformer grid south-east
    for r in range(3):
        for c in range(5):
            p.append(_b(f"sw_{r}_{c}", "metal",
                        (58 + c * 9.0, -118 + r * 9.0, PAD_Z), (5.0, 5.0, 3.2)))
    p.append(_b("sw_pad", "pad", (76, -109, PAD_Z + 0.02), (58, 34, 0.1)))
    # cooling / chiller bank west of the switchyard
    for c in range(6):
        p.append(_b(f"chill_{c}", "metal", (-96 + c * 7.5, -118, PAD_Z), (6.0, 12.0, 4.0)))
    return p


def rooftop_plant(seed=7):
    """HVAC units, ducts and skylights scattered over the large flat roofs."""
    rnd = random.Random(seed)
    p = []
    decks = [
        (78, 78, 62, 58, 31.0),    # B hall
        (16, 22, 36, 34, 44.0),    # C tower
        (-40, 26, 60, 54, 23.0),   # D hall
        (-24, -26, 66, 32, 18.9),  # E block
    ]
    for di, (cx, cy, w, d, z) in enumerate(decks):
        for i in range(10):
            ux = cx + rnd.uniform(-w / 2 + 6, w / 2 - 6)
            uy = cy + rnd.uniform(-d / 2 + 6, d / 2 - 6)
            sx, sy = rnd.uniform(3.0, 7.0), rnd.uniform(3.0, 6.0)
            p.append(_b(f"hvac_{di}_{i}", "metal", (ux, uy, PAD_Z + z), (sx, sy, rnd.uniform(1.4, 2.8))))
    return p


# --- planting ---------------------------------------------------------------

def _tree(name, x, y, scale, mat="conifer"):
    h = 14.0 * scale
    return [
        _c(f"{name}_t", "trunk", (x, y, PAD_Z - 1.0), 0.45 * scale, h * 0.3, seg=6),
        {"type": "cone", "name": f"{name}_c", "mat": mat, "pos": (x, y, PAD_Z - 1.0 + h * 0.22),
         "radius": 3.1 * scale, "height": h * 0.85, "seg": 7},
    ]


def forest(seed=11, count=2400):
    """Dense conifer belt filling everything outside the campus verge."""
    rnd = random.Random(seed)
    p = []
    inner_x, inner_y = SITE_W / 2 + 30, SITE_D / 2 + 30
    n = 0
    guard = 0
    while n < count and guard < count * 40:
        guard += 1
        x = rnd.uniform(-GROUND / 2 + 20, GROUND / 2 - 20)
        y = rnd.uniform(-GROUND / 2 + 20, GROUND / 2 - 20)
        if abs(x) < inner_x and abs(y) < inner_y:
            continue                      # keep the campus and its verge clear
        if abs(y + 196) < 20 and abs(x + 40) < 460:
            continue                      # public road corridor
        if abs(x + 232) < 18:
            continue                      # branch road corridor
        p += _tree(f"ft{n}", x, y, rnd.uniform(0.85, 1.6))
        n += 1
    return p


def landscaping(seed=23):
    """Street trees, hedges and planters inside the campus."""
    rnd = random.Random(seed)
    p = []
    # street trees along the internal north-south spine
    for i in range(16):
        y = -96 + i * 12.5
        p += _tree(f"st_w{i}", -66, y, rnd.uniform(0.45, 0.6))
        p += _tree(f"st_e{i}", -50, y, rnd.uniform(0.45, 0.6))
    # trees along the public road frontage
    for i in range(26):
        p += _tree(f"rd{i}", -300 + i * 22.0, -178, rnd.uniform(0.5, 0.7))
    # hedge bands framing the lawn
    p += [
        _b("hedge_n", "hedge", (-96, 61, PAD_Z), (86, 2.4, 1.6)),
        _b("hedge_s", "hedge", (-96, 7, PAD_Z), (86, 2.4, 1.6)),
        _b("hedge_w", "hedge", (-140, 34, PAD_Z), (2.4, 52, 1.6)),
    ]
    # planter row between the parking apron and the buildings
    for i in range(9):
        p += _tree(f"pk{i}", -152 + i * 9.5, -58, rnd.uniform(0.4, 0.55))
    return p


def boundary():
    """Perimeter wall and light poles."""
    p = []
    hw, hd, t, h = SITE_W / 2, SITE_D / 2, 0.6, 2.8
    p += [
        _b("wall_n", "grey_wall", (0, hd, PAD_Z), (SITE_W + t, t, h)),
        _b("wall_s", "grey_wall", (0, -hd, PAD_Z), (SITE_W + t, t, h)),
        _b("wall_w", "grey_wall", (-hw, 0, PAD_Z), (t, SITE_D, h)),
        _b("wall_e", "grey_wall", (hw, 0, PAD_Z), (t, SITE_D, h)),
    ]
    for i in range(12):
        x = -hw + 8 + i * (SITE_W - 16) / 11.0
        for y in (hd - 8, -hd + 8):
            p.append(_c(f"pole_{i}_{y:.0f}", "metal", (x, y, PAD_Z), 0.3, 11.0, seg=8))
    return p


# --- assembly ---------------------------------------------------------------

def layout(include_forest=True):
    p = []
    p += terrain()
    p += roads()
    p += buildings()
    p += process_equipment()
    p += rooftop_plant()
    p += boundary()
    p += landscaping()
    if include_forest:
        p += forest()
    return p


# Camera matching the reference render: high oblique from the south-west,
# roughly 38 degrees above the horizon, long lens so the site reads flat.
CAMERA = {
    "location": (-395.0, -510.0, 395.0),
    "target": (-4.0, 14.0, 16.0),
    "lens_mm": 64.0,
}

SUN = {"elevation_deg": 42.0, "azimuth_deg": 128.0, "strength": 3.2}


if __name__ == "__main__":
    prims = layout()
    per_mat = {}
    for q in prims:
        per_mat[q["mat"]] = per_mat.get(q["mat"], 0) + 1
    print(f"{len(prims)} primitives across {len(per_mat)} materials")
    for k in sorted(per_mat, key=lambda m: -per_mat[m]):
        print(f"  {k:12s} {per_mat[k]}")
