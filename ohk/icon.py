"""Icon generation for OHK."""

from PIL import Image, ImageDraw


def make_icon(size=64):
    """Draw a crisp mouse cursor icon at the given size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64.0

    cursor = [
        (8*s, 4*s), (8*s, 52*s), (20*s, 40*s),
        (32*s, 56*s), (38*s, 52*s), (26*s, 36*s),
        (40*s, 34*s), (8*s, 4*s),
    ]
    d.polygon(cursor, fill=(30, 30, 30, 255), outline=(255, 255, 255, 255),
              width=max(1, int(2*s)))
    return img
