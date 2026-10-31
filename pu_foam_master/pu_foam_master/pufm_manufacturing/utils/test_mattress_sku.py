# Copyright (c) 2026, PU Foam Master and contributors

import unittest

from pu_foam_master.pufm_manufacturing.utils.mattress_sku import (
	build_item_code,
	parse_product_line_from_item_code,
	sanitize_sku_token,
)


class TestMattressSku(unittest.TestCase):
	def test_sanitize_token(self):
		self.assertEqual(sanitize_sku_token(" Happi Orthopedic "), "Happi-Orthopedic")

	def test_build_item_code(self):
		self.assertEqual(
			build_item_code("Celefina", 75, 42, 8, "-FQ"),
			"Celefina-75x42x8-FQ",
		)

	def test_parse_product_line(self):
		self.assertEqual(
			parse_product_line_from_item_code("Orthopedic-75x42x8-FQ"),
			"Orthopedic",
		)
		self.assertEqual(
			parse_product_line_from_item_code("Super-Legend-6x3x8-CORE"),
			"Super-Legend",
		)
		self.assertIsNone(parse_product_line_from_item_code("invalid"))
