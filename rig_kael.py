"""Cut Kael's character sheet (characters/kael/sheet-3.webp) into rig parts -> characters/kael/parts/*.png.

Parts are found automatically (separate shapes on the white sheet); the table below names the ones the rig uses.
"""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as nd

from stories.series import ROOT

DIR = ROOT / "characters" / "kael"
NAMES = {  # sheet-3 shape boxes (x0, y0, x1, y1) -> part name
    "head": (657, 25, 841, 308), "torso": (613, 437, 826, 728),
    "sleeve": (849, 460, 910, 609), "forearm": (932, 460, 999, 605), "hand_open": (1136, 528, 1208, 642), "hand_point": (1230, 551, 1318, 608),
    "hand_fist": (1354, 546, 1411, 603), "leg": (965, 637, 1032, 991),
    "eye_l": (1156, 152, 1218, 196), "eye_r": (1245, 153, 1319, 196),
    "eye_l_half": (1366, 164, 1429, 194), "eye_r_half": (1455, 165, 1514, 194),
    "eye_l_shut": (1165, 249, 1222, 285), "eye_r_shut": (1251, 249, 1312, 285),
    "m_rest": (656, 379, 729, 386), "m_A": (762, 363, 839, 400), "m_E": (874, 369, 956, 396),
    "m_O": (994, 363, 1066, 399), "m_wide": (1109, 365, 1196, 399), "m_teeth": (1234, 368, 1327, 393),
}
# the drawn face on the head, painted over with skin so swappable eyes and mouths can sit there (sheet coords)
FACE_PATCHES = [(700, 124, 742, 158), (760, 124, 802, 158), (732, 196, 774, 211)]


def main():
    src = Image.open(DIR / "sheet-3.webp").convert("RGB")
    a = np.asarray(src).astype(np.int16)
    mask = nd.binary_fill_holes(nd.binary_closing(a.min(axis=2) < 232, iterations=2))
    out = DIR / "parts"
    out.mkdir(exist_ok=True)
    img = src.copy()
    arr = np.asarray(img).copy()
    for x0, y0, x1, y1 in FACE_PATCHES:  # skin fill from the patch border, then blur so it blends
        ring = np.concatenate([arr[y0 - 3:y0, x0:x1].reshape(-1, 3), arr[y1:y1 + 3, x0:x1].reshape(-1, 3)])
        arr[y0:y1, x0:x1] = np.median(ring, axis=0)
    img = Image.fromarray(arr)
    soft = img.filter(ImageFilter.GaussianBlur(3))
    for x0, y0, x1, y1 in FACE_PATCHES:
        img.paste(soft.crop((x0 - 2, y0 - 2, x1 + 2, y1 + 2)), (x0 - 2, y0 - 2))
    for name, (x0, y0, x1, y1) in NAMES.items():
        x0, y0, x1, y1 = x0 - 3, y0 - 3, x1 + 3, y1 + 3
        m = mask[y0:y1, x0:x1]
        lab, _ = nd.label(m)
        c = lab[lab.shape[0] // 2, lab.shape[1] // 2] or np.bincount(lab[lab > 0]).argmax()
        m = nd.binary_fill_holes(lab == c) if name not in ("hand_open", "hand_point", "hand_fist") else m
        m = nd.binary_erosion(m, iterations=2)          # drop the anti-aliased white rim
        rgb = np.asarray((img if name == "head" else src).crop((x0, y0, x1, y1))).copy()
        keep_white = name.startswith(("eye", "m_"))     # eye whites and teeth stay white
        if not keep_white:                              # near-white pixels take the nearest real colour
            limit = 175 if name.startswith("hand") else 205
            bad = (rgb.min(axis=2) > limit) | ~nd.binary_erosion(m, iterations=1)
            if name.startswith("hand"):                 # gaps between fingers: cut them out, not paint them
                m &= ~(rgb.min(axis=2) > limit)
                m = nd.binary_opening(m, iterations=1)
            if (~bad).any():
                idx = nd.distance_transform_edt(bad, return_distances=False, return_indices=True)
                rgb = rgb[idx[0], idx[1]]
        alpha = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9))
        piece = Image.fromarray(rgb).convert("RGBA")
        piece.putalpha(alpha)
        piece.save(out / f"{name}.png")
    print("parts:", len(NAMES))


if __name__ == "__main__":
    main()
