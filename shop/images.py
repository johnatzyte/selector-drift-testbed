"""Product imagery, rendered inline as SVG.

Deterministic from the sku, so a product looks the same on every run, and no request
ever leaves the page. Conference wifi cannot break these.
"""

import hashlib

from markupsafe import Markup

# Drawn in a 100 x 75 box, centred, stroked in white over the gradient.
GLYPHS = {
    "beans": '<ellipse cx="50" cy="37" rx="19" ry="13" transform="rotate(-25 50 37)"/><path d="M36 45c9-10 19-11 28-16" fill="none" stroke-width="2.5"/>',
    "decaf": '<ellipse cx="50" cy="37" rx="19" ry="13" transform="rotate(-25 50 37)"/><path d="M36 45c9-10 19-11 28-16" fill="none" stroke-width="2.5"/><path d="M33 22 67 52" fill="none" stroke-width="3"/>',
    "pods-capsules": '<path d="M38 20h24l-5 26a8 8 0 0 1-14 0z"/><rect x="35" y="15" width="30" height="6" rx="3"/>',
    "espresso-machines": '<rect x="26" y="16" width="48" height="40" rx="5"/><rect x="40" y="56" width="20" height="4" rx="2"/><circle cx="62" cy="26" r="4" fill="none" stroke-width="2.5"/><path d="M38 40h12v6H38z" fill="none" stroke-width="2.5"/>',
    "grinders": '<path d="M35 14h30l-5 18H40z"/><rect x="38" y="34" width="24" height="26" rx="4"/><circle cx="50" cy="46" r="5" fill="none" stroke-width="2.5"/>',
    "brewers": '<path d="M32 18h36L54 44h-8z"/><rect x="40" y="46" width="20" height="16" rx="3" fill="none" stroke-width="2.5"/>',
    "tampers-scales": '<rect x="44" y="14" width="12" height="20" rx="5"/><ellipse cx="50" cy="40" rx="20" ry="7"/><path d="M30 52h40" fill="none" stroke-width="2.5"/>',
    "filters": '<path d="M30 18h40L52 52h-4z" fill="none" stroke-width="3"/><path d="M38 28h24M42 36h16" fill="none" stroke-width="2.5"/>',
    "cleaning": '<rect x="44" y="12" width="12" height="26" rx="4"/><rect x="34" y="38" width="32" height="10" rx="3"/><path d="M38 48v10M46 48v10M54 48v10M62 48v10" fill="none" stroke-width="2.5"/>',
    "kettles": '<path d="M34 30h30v22a6 6 0 0 1-6 6H40a6 6 0 0 1-6-6z"/><path d="M64 34c10-2 12-12 6-18" fill="none" stroke-width="3"/><path d="M44 30v-6h10v6" fill="none" stroke-width="2.5"/>',
}


def svg_for(product, height=150):
    seed = int(hashlib.sha256(product["sku"].encode()).hexdigest()[:8], 16)
    hue = 160 + seed % 120
    glyph = GLYPHS.get(product["category"], GLYPHS["beans"])
    gid = f"g{product['sku'].replace('-', '')}"
    return Markup(
        f'<svg class="product-image" viewBox="0 0 100 75" height="{height}" role="img" '
        f'aria-label="{product["category_name"]}" preserveAspectRatio="xMidYMid slice">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue} 58% 63%)"/>'
        f'<stop offset="1" stop-color="hsl({hue + 24} 62% 44%)"/>'
        f"</linearGradient></defs>"
        f'<rect width="100" height="75" fill="url(#{gid})"/>'
        f'<g fill="#fff" stroke="#fff" fill-opacity=".85" stroke-opacity=".85" stroke-linejoin="round">{glyph}</g>'
        f"</svg>"
    )
