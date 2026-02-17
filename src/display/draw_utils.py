from PIL import ImageFont

from config import DEBUG, FONT_PATH


_font_cache = {}

def get_cached_font(size, font_path=FONT_PATH):
    cache_key = (size, font_path)
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    else:
        font = ImageFont.truetype(font_path, size)
        _font_cache[cache_key] = font
        return font


def get_text_dimensions(draw, text_string, font):
    bbox = draw.textbbox((0,0), text_string, font=font)
    if bbox:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        ascent = -bbox[1]
        if (ascent % 2 != 0):
            ascent = ascent + 1

        return (width, height, ascent)


#box: (x, y, width, height)
#align: "left", "center", "right"
def draw_aligned_text(draw, text, font_size, fill, box, align="left", halign="top", font_path=FONT_PATH, autoscale=False):
    x, y, width, height = box

    font = get_cached_font(font_size, font_path)
    text_width, text_height, ascent = get_text_dimensions(draw, text, font=font)
    new_font_size = font_size

    if (autoscale == True) and (text_width > width or text_height > height):
        scale = min(width / text_width, height / text_height)
        new_font_size = max(1, int(font.size * scale))
        font = get_cached_font(new_font_size)
        text_width, text_height, ascent = get_text_dimensions(draw, text, font=font)

    if align == "center":
        tx = x + (width - text_width) / 2
    elif align == "right":
        tx = x + (width - text_width)
    else:
        tx = x

    if halign == "top":
        ty = y + ascent
    elif halign == "center":
        ty = y + (height - text_height) / 2 + ascent
    else:
        ty = y + (height - text_height) + ascent

    if DEBUG != 0:
        draw.rectangle((x,y,x+width,y+height), outline=(255,0,0), width=1)
        bbox = draw.textbbox((tx, ty), text, font=font)
        draw.rectangle(bbox, outline=(0,255,0), width=1)

    draw.text((tx, ty), text, font=font, fill=fill)
