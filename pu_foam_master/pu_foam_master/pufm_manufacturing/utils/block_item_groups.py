"""Item Group resolution for foam block Items created from Density Configuration."""

from __future__ import annotations

import re

import frappe
from frappe import _

GROUP_MATTRESS = "Mattress Blocks"
GROUP_B = "B Blocks"
GROUP_HAPPI = "Happi Blocks"

_SETTINGS_FALLBACKS = ("Raw Material", "Products")


def infer_block_item_group_from_density_name(density_name: str) -> str | None:
	"""
	Map density_name to a leaf block Item Group (same rules as block reclass import).

	Returns None when no rule matches.
	"""
	code = (density_name or "").strip()
	if not code:
		return None
	upper = code.upper()
	if upper.startswith("ECONOMY BLOCK") or upper.startswith("POWER BLOCK"):
		return GROUP_B
	if re.match(r"^D\d", code, re.I):
		return GROUP_HAPPI
	if code.startswith("Standard") or code.startswith("Great"):
		return GROUP_MATTRESS
	if code.startswith("Legend") or code.startswith("Kings"):
		return GROUP_MATTRESS
	return None


def resolve_block_item_group(density_name: str, config_item_group: str | None = None) -> str:
	"""
	Resolve Item Group for new block / virtual Items.

	Priority: Density Configuration link → naming rules → Pufm Manufacturing Settings
	→ Raw Material / Products.
	"""
	candidates: list[str] = []

	if config_item_group and str(config_item_group).strip():
		candidates.append(str(config_item_group).strip())

	inferred = infer_block_item_group_from_density_name(density_name)
	if inferred:
		candidates.append(inferred)

	settings_group = frappe.db.get_single_value("Pufm Manufacturing Settings", "block_item_group")
	if settings_group:
		candidates.append(settings_group)

	candidates.extend(_SETTINGS_FALLBACKS)

	seen = set()
	for name in candidates:
		if not name or name in seen:
			continue
		seen.add(name)
		if frappe.db.exists("Item Group", name):
			return name

	frappe.throw(
		_(
			"Could not resolve Block Item Group for density {0}. "
			"Set Block Item Group on the Density Configuration or in Pufm Manufacturing Settings."
		).format(density_name or "?")
	)