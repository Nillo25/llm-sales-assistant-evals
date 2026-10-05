"""Product catalog and FAQ: loading and rendering into grounding context."""
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: Decimal
    colors: tuple[str, ...]
    specs: tuple[tuple[str, str], ...]
    description: str


@dataclass(frozen=True)
class FaqItem:
    question: str
    answer: str


def load_catalog(path: Path = DATA_DIR / "catalog.yaml") -> list[Product]:
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Product(
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            price=Decimal(str(row["price"])),
            colors=tuple(row.get("colors", ())),
            specs=tuple((str(k), _spec_value(v)) for k, v in row.get("specs", {}).items()),
            description=row["description"],
        )
        for row in rows
    ]


def _spec_value(value: object) -> str:
    # YAML 1.1 reads bare Yes/No as booleans; keep the words the catalog author wrote.
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def load_faq(path: Path = DATA_DIR / "faq.yaml") -> list[FaqItem]:
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [FaqItem(question=row["question"], answer=row["answer"]) for row in rows]


def format_price(price: Decimal) -> str:
    return f"${price:.2f}"


def render_product(product: Product) -> str:
    lines = [
        f"[{product.sku}] {product.name}",
        f"Category: {product.category}",
        f"Price: {format_price(product.price)}",
    ]
    if product.colors:
        lines.append(f"Colors: {', '.join(product.colors)}")
    if product.specs:
        lines.append("Specs:")
        lines.extend(f"- {key}: {value}" for key, value in product.specs)
    lines.append(product.description)
    return "\n".join(lines)


def render_faq(items: list[FaqItem]) -> str:
    return "\n\n".join(f"Q: {item.question}\nA: {item.answer}" for item in items)


def render_overview(products: list[Product]) -> str:
    """Product names grouped by category, without details.

    Used as the fallback context when retrieval finds nothing specific: it shows
    the model the range of products at a fraction of the full catalog's size.
    """
    by_category: dict[str, list[str]] = {}
    for product in products:
        by_category.setdefault(product.category, []).append(product.name)
    return "\n\n".join(
        f"{category}:\n" + "\n".join(f"- {name}" for name in names) for category, names in by_category.items()
    )
