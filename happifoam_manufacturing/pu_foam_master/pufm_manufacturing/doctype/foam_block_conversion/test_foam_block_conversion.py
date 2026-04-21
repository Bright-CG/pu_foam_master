# Copyright (c) 2026, Bright and Contributors
# See license.txt

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase


class TestFoamBlockConversion(FrappeTestCase):
	pass



class FoamBlockConversion(Document):
    def validate(self):
        if not self.processed_by:
            self.processed_by = frappe.session.user
