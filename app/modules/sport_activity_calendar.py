from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Mapping

import matplotlib
from PIL import Image, ImageDraw, ImageFont

from app.modules.sport_amount import format_sport_amount


# Палитра повторяет тёмную тему GitHub, чтобы календарь привычно читался в Discord.
BACKGROUND_COLOR = "#0D1117"
CARD_COLOR = "#161B22"
BORDER_COLOR = "#30363D"
TEXT_COLOR = "#F0F6FC"
MUTED_TEXT_COLOR = "#8B949E"
ACTIVITY_COLORS = ("#21262D", "#0E4429", "#006D32", "#26A641", "#39D353")

MONTH_NAMES = (
    "янв.",
    "февр.",
    "март",
    "апр.",
    "май",
    "июнь",
    "июль",
    "авг.",
    "сент.",
    "окт.",
    "нояб.",
    "дек.",
)
WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Загружает шрифт с кириллицей из комплекта matplotlib."""

    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / filename
    return ImageFont.truetype(str(font_path), size=size)


def _activity_level(amount: Decimal, maximum: Decimal) -> int:
    """Распределяет дневной результат по четырём уровням насыщенности."""

    if amount <= 0 or maximum <= 0:
        return 0
    ratio = amount / maximum
    if ratio <= Decimal("0.25"):
        return 1
    if ratio <= Decimal("0.5"):
        return 2
    if ratio <= Decimal("0.75"):
        return 3
    return 4


def render_sport_activity_calendar(
    activity_by_day: Mapping[date, int | float | Decimal],
    period_start: date,
    period_end: date,
    unit_name: str,
) -> BytesIO:
    """Рисует годовой PNG-календарь активности в стиле GitHub."""

    if period_end < period_start:
        raise ValueError("Конец периода календаря не может быть раньше начала.")

    grid_start = period_start - timedelta(days=period_start.weekday())
    grid_end = period_end + timedelta(days=6 - period_end.weekday())
    week_count = (grid_end - grid_start).days // 7 + 1

    cell_size = 13
    cell_gap = 4
    cell_step = cell_size + cell_gap
    grid_left = 76
    grid_top = 112
    image_width = max(960, grid_left + week_count * cell_step + 38)
    image_height = 292

    image = Image.new("RGB", (image_width, image_height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (8, 8, image_width - 8, image_height - 8),
        radius=14,
        fill=CARD_COLOR,
        outline=BORDER_COLOR,
        width=1,
    )

    title_font = _font(22, bold=True)
    regular_font = _font(13)
    small_font = _font(11)
    small_bold_font = _font(11, bold=True)

    draw.text((28, 24), "Календарь активности", font=title_font, fill=TEXT_COLOR)
    draw.text(
        (28, 56),
        f"{period_start:%d.%m.%Y} — {period_end:%d.%m.%Y}",
        font=regular_font,
        fill=MUTED_TEXT_COLOR,
    )

    # Название месяца ставится над неделей, в которой начинается новый месяц.
    previous_month = None
    for week_index in range(week_count):
        week_start = grid_start + timedelta(days=week_index * 7)
        visible_days = [week_start + timedelta(days=offset) for offset in range(7)]
        month_day = next(
            (
                day
                for day in visible_days
                if period_start <= day <= period_end and day.month != previous_month
            ),
            None,
        )
        if month_day is not None:
            x = grid_left + week_index * cell_step
            draw.text(
                (x, 88),
                MONTH_NAMES[month_day.month - 1],
                font=small_font,
                fill=MUTED_TEXT_COLOR,
            )
            previous_month = month_day.month

    for weekday, label in enumerate(WEEKDAY_NAMES):
        y = grid_top + weekday * cell_step - 1
        draw.text((30, y), label, font=small_font, fill=MUTED_TEXT_COLOR)

    decimal_activity = {
        day: Decimal(str(amount))
        for day, amount in activity_by_day.items()
    }
    maximum = max(
        (amount for amount in decimal_activity.values() if amount > 0),
        default=Decimal("0"),
    )
    active_days = 0
    total_amount = Decimal("0")
    for week_index in range(week_count):
        for weekday in range(7):
            current_day = grid_start + timedelta(days=week_index * 7 + weekday)
            if not period_start <= current_day <= period_end:
                continue

            amount = max(Decimal("0"), decimal_activity.get(current_day, Decimal("0")))
            if amount:
                active_days += 1
                total_amount += amount
            level = _activity_level(amount, maximum)
            x = grid_left + week_index * cell_step
            y = grid_top + weekday * cell_step
            draw.rounded_rectangle(
                (x, y, x + cell_size, y + cell_size),
                radius=2,
                fill=ACTIVITY_COLORS[level],
            )

    stats_y = 247
    draw.text(
        (30, stats_y),
        (
            f"Дней с активностью: {active_days}  ·  "
            f"Всего: {format_sport_amount(total_amount, thousands_separator=' ')} {unit_name}"
        ),
        font=small_bold_font,
        fill=MUTED_TEXT_COLOR,
    )

    legend_x = image_width - 208
    draw.text((legend_x, stats_y), "Меньше", font=small_font, fill=MUTED_TEXT_COLOR)
    legend_x += 54
    for color in ACTIVITY_COLORS:
        draw.rounded_rectangle(
            (legend_x, stats_y, legend_x + 12, stats_y + 12),
            radius=2,
            fill=color,
        )
        legend_x += 16
    draw.text((legend_x + 2, stats_y), "Больше", font=small_font, fill=MUTED_TEXT_COLOR)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
