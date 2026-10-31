# Copyright (c) 2026, PU Foam Master and contributors

import unittest

from pu_foam_master.pufm_manufacturing.utils.mattress_sku import policy_document_name


class TestMattressBrandPolicyNaming(unittest.TestCase):
	def test_policy_document_name(self):
		self.assertEqual(policy_document_name("HappiFoam", "Orthopedic"), "HappiFoam-Orthopedic")
		self.assertEqual(policy_document_name("HappiFoam", ""), "HappiFoam")
		self.assertEqual(policy_document_name("HappiFoam", None), "HappiFoam")
