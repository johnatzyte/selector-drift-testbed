"""Regenerate shop/data/catalogue.json.

Deterministic: same seed, same 500 products, byte-identical output. The app never
runs this — it only reads the committed JSON. Run it by hand if you want a new
catalogue, then commit the diff.

    uv run python tools/generate_catalogue.py
"""

import json
import random
import re
from pathlib import Path

SEED = 20260918
OUT = Path(__file__).resolve().parent.parent / "shop" / "data" / "catalogue.json"

SECTIONS = [
    ("coffee", "Coffee", [("beans", "Beans", 300), ("pods-capsules", "Pods & Capsules", 80), ("decaf", "Decaf", 70)]),
    ("equipment", "Equipment", [("espresso-machines", "Espresso Machines", 120), ("grinders", "Grinders", 100), ("brewers", "Brewers", 90)]),
    ("accessories", "Accessories", [("tampers-scales", "Tampers & Scales", 70), ("filters", "Filters", 60), ("cleaning", "Cleaning", 60), ("kettles", "Kettles", 50)]),
]
TOTAL = sum(count for _, _, cats in SECTIONS for _, _, count in cats)

ROASTERS = ["Ardent", "Blackbird", "Cloudberry", "Drift House", "Ember Lane", "Foxglove", "Gable Street", "Harbourside", "Ironwood", "Juniper & Co", "Kestrel", "Lantern Works", "Midland", "Northvale", "Orchard Row", "Pellucid", "Quarry Road", "Redstone", "Saltwind", "Thicket", "Umbra", "Verdigris", "Westerly", "Yardarm", "Zephyr"]
ORIGINS = ["Ethiopia Yirgacheffe", "Ethiopia Guji", "Kenya Nyeri", "Kenya Kirinyaga", "Colombia Huila", "Colombia Narino", "Brazil Cerrado", "Guatemala Antigua", "Costa Rica Tarrazu", "Rwanda Nyamasheke", "Burundi Kayanza", "Peru Cajamarca", "Honduras Marcala", "Panama Boquete", "Indonesia Sumatra", "Papua New Guinea", "El Salvador Santa Ana", "Mexico Chiapas", "Bolivia Caranavi", "Tanzania Mbeya"]
PROCESSES = ["Washed", "Natural", "Honey", "Anaerobic Natural", "Wet-Hulled", "Carbonic Maceration"]
ROASTS = ["Light", "Light-Medium", "Medium", "Medium-Dark", "Dark"]
WEIGHTS = ["250g", "500g", "1kg"]
NOTES = ["blackcurrant", "milk chocolate", "jasmine", "toffee", "stone fruit", "brown sugar", "bergamot", "red apple", "hazelnut", "dried fig", "cocoa nib", "peach", "lime zest", "praline", "blueberry", "molasses", "orange blossom", "almond"]

POD_BRANDS = ["Altura", "Bricco", "Caffe Nero Lane", "Doppio", "Estrella", "Fumo", "Granello", "Hestia", "Incanto", "Lucente", "Meridio", "Nocturno"]
POD_FLAVOURS = ["Ristretto", "Lungo", "Intenso", "Forte", "Dolce", "Crema", "Napoli", "Roma", "Firenze", "Decaffeinato", "Milano", "Sereno"]
POD_COMPAT = ["Nespresso Original", "Nespresso Vertuo", "Dolce Gusto", "Illy iperEspresso", "Lavazza A Modo Mio"]

HW_BRANDS = ["Bellacqua", "Corsair", "Duomo", "Ferro", "Grisaglia", "Helvetic", "Iserlohn", "Kestrel Works", "Lumiere", "Marchetti", "Novara", "Ottimo", "Praxis", "Quadrante", "Rivolta", "Stellar", "Torrente", "Ulmus", "Vulcano", "Windlass"]
MACHINE_MODELS = ["Uno", "Duo", "Tre", "Classic", "Leva", "Domo", "Studio", "Atelier", "Vantage", "Meridian", "Pursuit", "Forte"]
BOILERS = ["Single boiler", "Heat exchanger", "Dual boiler", "Thermoblock", "Thermocoil"]
GRINDER_MODELS = ["Axis", "Basalt", "Cadence", "Delta", "Ember", "Flint", "Gradient", "Halo", "Index", "Jet"]
BURRS = ["64mm flat steel", "58mm flat steel", "38mm conical steel", "48mm conical steel", "83mm flat titanium-coated", "40mm conical ceramic"]
BREWER_TYPES = ["Pour-Over Cone", "Chambered Brewer", "French Press", "Immersion Brewer", "Siphon Brewer", "Cold Brew Tower", "Moka Pot", "Percolator", "Flat-Bottom Dripper"]
MATERIALS = ["Borosilicate glass", "Stainless steel", "Ceramic", "Copper", "Tritan plastic", "Walnut and steel"]

TAMPER_ITEMS = ["Calibrated Tamper", "Precision Tamper", "Distribution Tool", "Levelling Tool", "Bench Scale", "Brew Scale", "Pocket Scale", "Dosing Cup", "WDT Tool", "Tamping Mat"]
FILTER_ITEMS = ["Paper Filters", "Bleached Filters", "Natural Filters", "Metal Mesh Filter", "Cloth Filter", "Precision Basket", "Puck Screen", "Bottomless Basket"]
CLEANING_ITEMS = ["Backflush Detergent", "Descaler Sachets", "Group Head Brush", "Grinder Brush", "Cleaning Tablets", "Milk Line Cleaner", "Microfibre Cloths", "Knock Box"]
KETTLE_ITEMS = ["Gooseneck Kettle", "Variable Temperature Kettle", "Stovetop Gooseneck", "Pour-Over Kettle", "Travel Kettle"]

SIZES = ["58mm", "53mm", "51mm", "54mm"]
CAPACITIES = ["0.6L", "0.8L", "1.0L", "1.2L", "1.7L"]

PRICE_RANGES = {
    "beans": (9, 34), "pods-capsules": (5, 22), "decaf": (10, 30),
    "espresso-machines": (189, 2850), "grinders": (95, 1450), "brewers": (18, 320),
    "tampers-scales": (12, 185), "filters": (4, 65), "cleaning": (6, 78), "kettles": (29, 210),
}


def slugify(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


MATERIAL_BY_KEYWORD = [
    (("Paper", "Bleached"), ["Bleached paper"]),
    (("Natural Filters",), ["Natural paper"]),
    (("Cloth",), ["Organic cotton"]),
    (("Mesh", "Screen", "Basket"), ["Stainless mesh", "Etched steel"]),
    (("Detergent", "Cleaner"), ["Food-safe powder", "Citric acid solution"]),
    (("Descaler",), ["Citric acid solution", "Food-safe powder"]),
    (("Tablets",), ["Effervescent tablet"]),
    (("Brush",), ["Nylon bristle"]),
    (("Cloths",), ["Microfibre"]),
    (("Knock Box",), ["Powder-coated steel"]),
    (("Mat",), ["Silicone"]),
    (("Scale",), ["Tritan plastic", "Stainless steel"]),
    (("Tamper", "Tool", "Cup"), ["Stainless steel", "Anodised aluminium", "Walnut and steel"]),
    (("Kettle",), ["Stainless steel", "Copper", "Powder-coated steel"]),
]


def material_for(name, rng, fallback):
    for keywords, options in MATERIAL_BY_KEYWORD:
        if any(k in name for k in keywords):
            return rng.choice(options)
    return rng.choice(fallback)


def specs_for(category, rng, name):
    if category in ("beans", "decaf"):
        return {
            "Origin": next(o for o in ORIGINS if o in name),
            "Roast": rng.choice(ROASTS),
            "Weight": rng.choice(WEIGHTS),
            "Process": rng.choice(PROCESSES),
            "Tasting notes": ", ".join(rng.sample(NOTES, 3)),
        }
    if category == "pods-capsules":
        return {
            "Compatibility": rng.choice(POD_COMPAT),
            "Pack size": f"{rng.choice([10, 16, 20, 30, 50, 100])} capsules",
            "Intensity": f"{rng.randint(4, 13)}/13",
        }
    if category == "espresso-machines":
        return {
            "Wattage": f"{rng.choice([1050, 1200, 1350, 1450, 1600, 1800])}W",
            "Boiler": rng.choice(BOILERS),
            "Pressure": f"{rng.choice([9, 12, 15])} bar",
            "Warranty": f"{(y := rng.choice([1, 2, 3, 5]))} year{'s' if y > 1 else ''}",
            "Dimensions": f"{rng.randint(22, 38)} x {rng.randint(28, 46)} x {rng.randint(30, 44)} cm",
        }
    if category == "grinders":
        return {
            "Burr type": rng.choice(BURRS),
            "Settings": f"{rng.choice([15, 25, 40, 60, 'Stepless'])}",
            "Hopper": f"{rng.choice([60, 120, 250, 350, 500])}g",
            "Motor": f"{rng.choice([90, 120, 150, 250, 350])}W",
        }
    if category == "brewers":
        return {
            "Capacity": f"{rng.choice([1, 2, 3, 4, 6, 8])} cup",
            "Material": rng.choice(MATERIALS),
            "Brew method": rng.choice(["Pour over", "Immersion", "Pressure", "Vacuum", "Cold extraction"]),
        }
    if category == "kettles":
        return {
            "Material": material_for(name, rng, ["Stainless steel", "Copper"]),
            "Capacity": rng.choice(CAPACITIES),
            "Compatibility": rng.choice(["All hobs", "Induction ready", "Electric base", "Gas and electric"]),
        }
    if category == "cleaning":
        return {
            "Material": material_for(name, rng, ["Food-safe powder", "Nylon bristle"]),
            "Compatibility": rng.choice(["All espresso machines", "Most portafilters", "Universal", "Grinders and hoppers"]),
            "Pack size": rng.choice(["100g", "250g", "30 tablets", "12 sachets", "Single unit", "Pack of 4"]),
        }
    if category == "filters":
        return {
            "Material": material_for(name, rng, ["Bleached paper", "Stainless mesh"]),
            "Compatibility": rng.choice(SIZES + ["Universal", "Most portafilters", "Size 02 cones", "Flat-bottom baskets"]),
            "Pack size": rng.choice(["100 sheets", "200 sheets", "Pack of 2", "Single unit", "Pack of 6"]),
        }
    return {
        "Material": material_for(name, rng, ["Stainless steel", "Anodised aluminium"]),
        "Compatibility": rng.choice(SIZES + ["Universal", "Most portafilters"]),
        "Dimensions": f"{rng.randint(4, 24)} x {rng.randint(4, 24)} x {rng.randint(2, 18)} cm",
    }


def names_for(category, count, rng):
    """Unique names, shuffled so a single page shows real variety.

    Drawing from a shuffled pool of every brand/model pair rather than indexing by
    position — otherwise page 1 of Beans is twenty-five Yirgacheffes in a row.
    """
    if category == "beans":
        pool = [f"{r} {o}" for r in ROASTERS for o in ORIGINS]
    elif category == "decaf":
        pool = [f"{r} {o} Decaf" for r in ROASTERS for o in ORIGINS]
    elif category == "pods-capsules":
        pool = [f"{b} {f} Capsules" for b in POD_BRANDS for f in POD_FLAVOURS]
    elif category == "espresso-machines":
        pool = [f"{b} {m} {n}" for b in HW_BRANDS for m in MACHINE_MODELS for n in (80, 200, 500)]
    elif category == "grinders":
        pool = [f"{b} {m} Grinder" for b in HW_BRANDS for m in GRINDER_MODELS]
    elif category == "brewers":
        pool = [f"{b} {t}" for b in HW_BRANDS for t in BREWER_TYPES]
    else:
        items = {"tampers-scales": TAMPER_ITEMS, "filters": FILTER_ITEMS, "cleaning": CLEANING_ITEMS, "kettles": KETTLE_ITEMS}[category]
        pool = [f"{b} {i}" for b in HW_BRANDS for i in items]

    assert len(pool) >= count, f"{category}: pool of {len(pool)} cannot fill {count}"
    rng.shuffle(pool)
    return pool[:count]


def describe(category, name, specs, rng):
    if category in ("beans", "decaf"):
        return f"A {specs['Roast'].lower()} roast with notes of {specs['Tasting notes']}. {specs['Process']} process, roasted to order and shipped in {specs['Weight']} bags."
    if category == "pods-capsules":
        return f"{specs['Pack size']} for {specs['Compatibility']} machines, at intensity {specs['Intensity']}. An everyday cup with a steady crema."
    if category == "espresso-machines":
        return f"A {specs['Boiler'].lower()} machine rated at {specs['Wattage']}, delivering {specs['Pressure']} at the group. Covered by a {specs['Warranty'].split()[0]}-year warranty."
    if category == "grinders":
        return f"{specs['Burr type']} burrs driven by a {specs['Motor']} motor, with {specs['Settings']} grind settings and a {specs['Hopper']} hopper."
    if category == "brewers":
        return f"A {specs['Capacity']} {specs['Brew method'].lower()} brewer in {specs['Material'].lower()}. Built to sit on the counter and get used every morning."
    if category in ("cleaning", "filters"):
        return f"{specs['Material']}, supplied as {specs['Pack size'].lower()}, compatible with {specs['Compatibility'].lower()}. The unglamorous part of a good cup."
    return f"{specs['Material']} construction, sized for {specs['Compatibility'].lower()}. Built for daily use in a home or small shop setup."


ALL_BRANDS = sorted(set(ROASTERS + POD_BRANDS + HW_BRANDS), key=len, reverse=True)


def brand_of(name):
    """Longest matching brand, so "Juniper & Co" and "Drift House" stay whole."""
    return next(b for b in ALL_BRANDS if name.startswith(b))


def main():
    rng = random.Random(SEED)
    products = []
    for section_slug, section_name, categories in SECTIONS:
        for cat_slug, cat_name, count in categories:
            lo, hi = PRICE_RANGES[cat_slug]
            names = names_for(cat_slug, count, rng)
            for i, name in enumerate(names):
                specs = specs_for(cat_slug, rng, name)
                price = round(rng.uniform(lo, hi), 2)
                price = float(int(price)) + rng.choice([0.0, 0.5, 0.95, 0.99, 0.25])
                products.append({
                    "sku": f"{cat_slug[:3].upper()}-{i + 1:04d}",
                    "slug": f"{slugify(name)}-{cat_slug[:3]}{i + 1:03d}",
                    "name": name,
                    "brand": brand_of(name),
                    "section": section_slug,
                    "section_name": section_name,
                    "category": cat_slug,
                    "category_name": cat_name,
                    "price": price,
                    "currency": "GBP",
                    "rating": round(rng.uniform(3.0, 5.0), 1),
                    "reviews": rng.randint(0, 840),
                    "stock": rng.choice([0, 0] + list(range(1, 120))),
                    "specs": specs,
                    "description": describe(cat_slug, name, specs, rng),
                })

    slugs = [p["slug"] for p in products]
    assert len(set(slugs)) == len(slugs), "duplicate slugs"
    assert len(products) == TOTAL, f"expected {TOTAL} products, got {len(products)}"

    OUT.write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(products)} products to {OUT}")


if __name__ == "__main__":
    main()
