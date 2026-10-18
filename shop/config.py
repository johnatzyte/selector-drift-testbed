"""The live selector configuration.

Every class name, tag name and value placement in the site comes from here. The
templates and the stylesheet both render from the same dict, which is what keeps the
page looking identical while the markup underneath it changes.
"""

import re
import threading

IDENT_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
ATTR_RE = re.compile(r"^data-[a-z][a-z0-9-]{0,35}$")
CARD_FIELDS = ("title", "price", "rating", "stock")

DEFAULTS = {
    # class names
    "grid_class": "product-grid",
    "card_class": "product-card",
    "title_class": "product-title",
    "price_class": "price",
    "link_class": "product-link",
    "rating_class": "rating",
    "stock_class": "stock",
    "next_page_class": "next",
    "breadcrumb_class": "breadcrumb",
    "subnav_class": "subnav",
    "spec_class": "spec",
    "spec_label_class": "spec-label",
    "spec_value_class": "spec-value",
    # structure
    "title_tag": "h3",
    "card_tag": "article",
    "extra_wrapper": False,
    "price_in_attribute": False,
    "price_split": False,
    "id_to_class": False,
    "sku_attribute": "data-sku",
    "field_order": "title,price,rating,stock",
}


class ValidationError(Exception):
    def __init__(self, key, reason):
        super().__init__(f"{key}: {reason}")
        self.key = key
        self.reason = reason


def validate_ident(key, value):
    if not isinstance(value, str) or not IDENT_RE.match(value):
        raise ValidationError(key, "must be a lowercase CSS identifier matching ^[a-z][a-z0-9-]{0,39}$")
    return value


def validate_attribute(key, value):
    if not isinstance(value, str) or not ATTR_RE.match(value):
        raise ValidationError(key, "must be a data-* attribute name, e.g. data-sku")
    return value


def validate_flag(key, value):
    if not isinstance(value, bool):
        raise ValidationError(key, "must be true or false")
    return value


def validate_enum(*options):
    def check(key, value):
        if value not in options:
            raise ValidationError(key, f"must be one of {', '.join(options)}")
        return value

    return check


def validate_field_order(key, value):
    if not isinstance(value, str):
        raise ValidationError(key, "must be a comma-separated string")
    parts = [p.strip() for p in value.split(",")]
    if sorted(parts) != sorted(CARD_FIELDS):
        raise ValidationError(key, f"must be a permutation of {', '.join(CARD_FIELDS)}")
    return ",".join(parts)


SPEC = {
    # No "a": the title sits inside the card's anchor, and a nested <a> gets
    # reparented by the HTML parser, which would visibly break the card.
    "title_tag": validate_enum("h2", "h3", "h4", "div", "span", "p"),
    "card_tag": validate_enum("article", "div", "li", "section"),
    "extra_wrapper": validate_flag,
    "price_in_attribute": validate_flag,
    "price_split": validate_flag,
    "id_to_class": validate_flag,
    "sku_attribute": validate_attribute,
    "field_order": validate_field_order,
}
for _key in DEFAULTS:
    SPEC.setdefault(_key, validate_ident)


class UnknownKeys(Exception):
    def __init__(self, keys):
        super().__init__(f"unknown keys: {', '.join(keys)}")
        self.keys = keys


class SelectorStore:
    """Holds the current config. Mutations are validated in full, then applied atomically."""

    def __init__(self, defaults=None):
        self._defaults = dict(defaults or DEFAULTS)
        self._config = dict(self._defaults)
        self._version = 0
        self._history = {0: dict(self._config)}
        self._lock = threading.Lock()

    @property
    def version(self):
        return self._version

    def snapshot(self):
        with self._lock:
            return dict(self._config)

    def capture(self, version=None):
        """Return configuration and revision together under the same lock."""
        with self._lock:
            revision = self._version if version is None else version
            return dict(self._history[revision]), revision

    def _remember(self):
        self._history[self._version] = dict(self._config)
        # Keep recent CSS revisions without unbounded memory growth.
        if len(self._history) > 256:
            del self._history[min(self._history)]

    def defaults(self):
        return dict(self._defaults)

    def diff(self):
        current = self.snapshot()
        return {
            key: {"from": self._defaults[key], "to": current[key]}
            for key in self._defaults
            if current[key] != self._defaults[key]
        }

    def patch(self, changes, *, replace=False):
        if not isinstance(changes, dict):
            raise ValidationError("body", "must be a JSON object of selector keys")
        unknown = [k for k in changes if k not in SPEC]
        if unknown:
            raise UnknownKeys(sorted(unknown))
        validated = {key: SPEC[key](key, value) for key, value in changes.items()}
        with self._lock:
            if replace:
                self._config = dict(self._defaults)
            self._config.update(validated)
            self._version += 1
            self._remember()
        return self.snapshot()

    def reset(self):
        with self._lock:
            self._config = dict(self._defaults)
            self._version += 1
            self._remember()
        return self.snapshot()
