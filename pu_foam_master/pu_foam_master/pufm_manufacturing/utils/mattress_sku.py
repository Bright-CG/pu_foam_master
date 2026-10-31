# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Mattress / core SKU naming: product line prefix, size token, finish suffix."""

from __future__ import annotations

import re


def _flt(value):
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0

ITEM_CODE_SUFFIXES = ("-CORE", "-PLAIN", "-SQ", "-FQ")


def sanitize_sku_token(value):
	"""Safe token for item codes (alphanumeric, hyphen, underscore)."""
	token = "".join(
		ch if ch.isalnum() or ch in "-_" else "-" for ch in (value or "").strip()
	)
	return "-".join(part for part in token.split("-") if part)


def format_size_token(width, length, height):
	"""Build size token like 75x42x8 (drop trailing .0)."""

	def _fmt(number):
		val = _flt(number)
		if float(val).is_integer():
			return str(int(val))
		return f"{val:g}"

	return f"{_fmt(width)}x{_fmt(length)}x{_fmt(height)}"


def build_item_code(product_line, width, length, height, suffix):
	"""Naming standard: {product_line}-{size}{suffix}."""
	line = sanitize_sku_token(product_line)
	size = format_size_token(width, length, height)
	suffix = (suffix or "").strip()
	if line:
		return f"{line}-{size}{suffix}"
	return f"{size}{suffix}"


def strip_finish_suffix(item_code):
	code = (item_code or "").strip()
	if not code:
		return ""
	upper = code.upper()
	for suffix in ITEM_CODE_SUFFIXES:
		if upper.endswith(suffix):
			return code[: len(code) - len(suffix)]
	return code


def parse_product_line_from_item_code(item_code):
	"""Extract product line from a generator-style SKU (before -WxLxH)."""
	stem = strip_finish_suffix(item_code)
	if not stem or "x" not in stem:
		return None
	idx = stem.rfind("-")
	if idx <= 0:
		return None
	size_part = stem[idx + 1 :]
	if not re.match(r"^\d+(?:\.\d+)?x\d+(?:\.\d+)?x\d+(?:\.\d+)?$", size_part, re.I):
		return None
	return stem[:idx] or None


def get_product_line_for_item(item_code):
	"""Prefer Item.custom_product_line; fall back to parsing the item code."""
	if not item_code:
		return None
	import frappe

	if frappe.db.exists("Item", item_code):
		custom = (frappe.db.get_value("Item", item_code, "custom_product_line") or "").strip()
		if custom:
			return custom
	return parse_product_line_from_item_code(item_code)


def policy_document_name(brand, product_line=None):
	"""Mattress Brand Policy document name."""
	brand = (brand or "").strip()
	line = (product_line or "").strip()
	if line:
		return f"{brand}-{line}"
	return brand
