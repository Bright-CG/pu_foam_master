# Copyright (c) 2026, Bright and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from pu_foam_master.pufm_manufacturing.utils.block_item_groups import (
	GROUP_B,
	GROUP_HAPPI,
	GROUP_MATTRESS,
	infer_block_item_group_from_density_name,
)
from pu_foam_master.pufm_manufacturing.utils.density_bom import build_block_item_code


class TestBlockItemGroups(FrappeTestCase):
	def test_infer_happi_densities(self):
		for name in ("D13", "D20", "d14"):
			self.assertEqual(infer_block_item_group_from_density_name(name), GROUP_HAPPI)

	def test_infer_mattress_densities(self):
		self.assertEqual(infer_block_item_group_from_density_name("Standard"), GROUP_MATTRESS)
		self.assertEqual(infer_block_item_group_from_density_name("Great"), GROUP_MATTRESS)
		self.assertEqual(infer_block_item_group_from_density_name("Kings Block"), GROUP_MATTRESS)

	def test_infer_b_blocks(self):
		self.assertEqual(
			infer_block_item_group_from_density_name("Economy Block"), GROUP_B
		)
		self.assertEqual(infer_block_item_group_from_density_name("Power Block"), GROUP_B)

	def test_build_block_item_code_stable_for_duplicate_check(self):
		code_a = build_block_item_code("D13", 108, 75, 44)
		code_b = build_block_item_code("D13", 108, 75, 44)
		self.assertEqual(code_a, code_b)
		self.assertEqual(code_a, "D13-108x75x44 Block")