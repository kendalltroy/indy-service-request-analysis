"""Readable names for call types, which the data identifies by a
(keyword, subcategory) pair of lowercase strings."""

CALL_TYPE_LABELS = {
    ("abandoned vehicle", "private property (abv)"): "Abandoned Vehicle: Private Property",
    ("abandoned vehicle", "street (abv)"): "Abandoned Vehicle: Street",
    ("abandoned vehicle", "street/alley (abv)"): "Abandoned Vehicle: Street/Alley",
    ("alley", "brush/vegetation removal"): "Alley Brush Removal",
    ("animal", "abuse"): "Animal Abuse",
    ("animal", "dead"): "Dead Animal",
    ("animal", "stray (roam)"): "Stray Animal",
    ("chuckhole", "berm"): "Chuckhole: Berm",
    ("chuckhole", "street (chuckhole)"): "Street Chuckhole",
    ("graffiti: public/private property", "public property (graffiti)"): "Graffiti: Public Property",
    ("illegal dumping and junk/trash", "trash accumulation or dumped materials"): "Trash Dumping/Accumulation",
    ("new construction", "new sidewalk"): "New Sidewalk",
    ("new construction", "street resurfacing"): "Street Resurfacing",
    ("sidewalks/curbs", "broken"): "Broken Sidewalk/Curb",
    ("streets", "raised uneven surface"): "Uneven Street Surface",
    ("streets", "repair or install speed bump"): "Speed Bump Request",
    ("streets and alley repair", "berm"): "Street/Alley Repair: Berm",
    ("streets and alley repair", "raised uneven surface"): "Street/Alley Repair: Uneven Surface",
    ("trash", "96 gal cart - buy"): "Trash Cart Purchase",
    ("trash", "96 gal cart - other"): "Trash Cart: Other",
    ("trash", "96 gal cart - stolen"): "Stolen Trash Cart",
    ("trash", "96 gal trash (block)"): "Missed Trash Pickup: Block",
    ("trash", "96 gal trash (missed)"): "Missed Trash Pickup",
    ("trash", "heavy"): "Heavy Trash Pickup",
    ("weeds", "private property (complaint)"): "Weeds: Private Property",
}


def call_type_label(call_type):
    """Chart label for a (keyword, subcategory) pair. Call types that never
    reach a chart fall back to a title-cased "keyword / subcategory"."""
    return CALL_TYPE_LABELS.get(call_type, f"{call_type[0]} / {call_type[1]}".title())
