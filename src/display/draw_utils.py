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
def draw_aligned_text(draw, text, font_size, fill, box, align="left", halign="top",
                      font_path=FONT_PATH, autoscale=False, ref_text=None):
    x, y, width, height = box

    font = get_cached_font(font_size, font_path)

    if autoscale:
        sizing_text = ref_text or text
        sz_w, sz_h, _ = get_text_dimensions(draw, sizing_text, font=font)
        if sz_w > width or sz_h > height:
            scale = min(width / sz_w, height / sz_h)
            new_font_size = max(1, int(font.size * scale))
            font = get_cached_font(new_font_size, font_path)

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


def draw_multi_graph(draw, sensor_list, normalized_list, colors, graphbox):
    x1, y1, x2, y2 = graphbox

    # Horizontal grid dotted lines at 25%, 50%, 75%
    for pct in [0.25, 0.5, 0.75]:
        gy = int(y2 - (y2 - y1) * pct)
        for gx in range(x1, x2, 4):
            draw.point((gx, gy), fill=(35, 35, 35))

    # Each sensor line: glow then main
    for sensor_data, norm_data, color in zip(sensor_list, normalized_list, colors):
        if len(sensor_data.buffer) < 2:
            continue
        # Glow
        for i in range(1, len(sensor_data.buffer)):
            px1, py1 = i + x1, int(y2 - norm_data[i - 1])
            px2, py2 = i + x1 + 1, int(y2 - norm_data[i])
            glow = (color[0] // 4, color[1] // 4, color[2] // 4)
            draw.line((px1, py1, px2, py2), fill=glow, width=3)
        # Main line
        for i in range(1, len(sensor_data.buffer)):
            px1, py1 = i + x1, int(y2 - norm_data[i - 1])
            px2, py2 = i + x1 + 1, int(y2 - norm_data[i])
            draw.line((px1, py1, px2, py2), fill=color, width=2)


def draw_daily_graph(draw, histories, normalized_list, colors, graphbox, max_points=144):
    x1, y1, x2, y2 = graphbox

    # Horizontal grid dotted lines at 25%, 50%, 75%
    for pct in [0.25, 0.5, 0.75]:
        gy = int(y2 - (y2 - y1) * pct)
        for gx in range(x1, x2, 4):
            draw.point((gx, gy), fill=(35, 35, 35))

    # Vertical time markers at 6h, 12h, 18h from the oldest data point
    # Data fills left-to-right, so markers are relative to data length
    data_len = max((len(h) for h in histories), default=0)
    for hours in [6, 12, 18]:
        marker_pos = int(hours / 24 * max_points)
        tx = x1 + data_len - marker_pos
        if x1 <= tx <= x2:
            for ty in range(y1, y2, 4):
                draw.point((tx, ty), fill=(50, 50, 50))

    # Each sensor line, left-aligned
    for hist, norm, color in zip(histories, normalized_list, colors):
        if len(hist) < 2:
            continue
        x_off = 0
        # Glow
        for i in range(1, len(hist)):
            px1 = i - 1 + x1 + x_off
            py1 = int(y2 - norm[i - 1])
            px2 = i + x1 + x_off
            py2 = int(y2 - norm[i])
            glow = (color[0] // 4, color[1] // 4, color[2] // 4)
            draw.line((px1, py1, px2, py2), fill=glow, width=3)
        # Main line
        for i in range(1, len(hist)):
            px1 = i - 1 + x1 + x_off
            py1 = int(y2 - norm[i - 1])
            px2 = i + x1 + x_off
            py2 = int(y2 - norm[i])
            draw.line((px1, py1, px2, py2), fill=color, width=2)


def draw_graph(draw, sensor_data, normalized_data, graphbox):
    x1, y1, x2, y2 = graphbox

    # Horizontal grid dotted lines at 25%, 50%, 75%
    for pct in [0.25, 0.5, 0.75]:
        gy = int(y2 - (y2 - y1) * pct)
        for gx in range(x1, x2, 4):
            draw.point((gx, gy), fill=(35, 35, 35))

    # Gradient area fill — vertical line from curve to bottom at each x
    for i in range(len(sensor_data.buffer)):
        x = i + x1 + 1
        y_top = int(y2 - normalized_data[i])
        color = sensor_data.get_color_gradient(sensor_data.buffer[i])
        faded = (color[0] // 5, color[1] // 5, color[2] // 5)
        draw.line((x, y_top, x, y2), fill=faded, width=1)

    # Glow — wide dim line for depth effect
    for i in range(1, len(sensor_data.buffer)):
        px1, py1 = i + x1, int(y2 - normalized_data[i - 1])
        px2, py2 = i + x1 + 1, int(y2 - normalized_data[i])
        color = sensor_data.get_color_gradient(sensor_data.buffer[i])
        glow = (color[0] // 3, color[1] // 3, color[2] // 3)
        draw.line((px1, py1, px2, py2), fill=glow, width=5)

    # Main line — sharp, 2px
    for i in range(1, len(sensor_data.buffer)):
        px1, py1 = i + x1, int(y2 - normalized_data[i - 1])
        px2, py2 = i + x1 + 1, int(y2 - normalized_data[i])
        color = sensor_data.get_color_gradient(sensor_data.buffer[i])
        draw.line((px1, py1, px2, py2), fill=color, width=2)
