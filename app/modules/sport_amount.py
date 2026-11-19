from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


# Шесть знаков хватает для километров, часов и большинства спортивных метрик.
SPORT_AMOUNT_QUANT = Decimal("0.000001")
SPORT_AMOUNT_MAX = Decimal("9000000000000000000")


def normalize_sport_amount(value: str | int | float | Decimal) -> Decimal | None:
    """Преобразует ввод Discord в точное число с шестью знаками после точки."""

    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return None
        return amount.quantize(SPORT_AMOUNT_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


def format_sport_amount(
    value: int | float | Decimal,
    *,
    thousands_separator: str = ",",
) -> str:
    """Форматирует число без лишнего `.0`, сохраняя дробную часть при наличии."""

    amount = Decimal(str(value))
    plain = format(amount, "f")
    integer_part, separator, fraction_part = plain.partition(".")
    fraction_part = fraction_part.rstrip("0")
    grouped_integer = f"{int(integer_part):,}".replace(",", thousands_separator)
    if not separator or not fraction_part:
        return grouped_integer
    return f"{grouped_integer}.{fraction_part}"
