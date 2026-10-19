"""Release invariants: the complete offline asset set and stable bilingual IDs."""

from __future__ import annotations

import hashlib
import json
import struct
import unittest

from snowmm.core import paths
from snowmm.core.catalog import Catalog
from snowmm.i18n import TRANSLATIONS, armor_name, character_name, element_name, get_language, set_language


class ReleaseAssetsTests(unittest.TestCase):
    def test_every_portrait_has_a_verified_source_and_digest(self):
        manifest = json.loads(paths.asset("catalog", "artwork.json").read_text(encoding="utf-8"))
        entries = manifest["portraits"]
        self.assertEqual({entry["name"] for entry in entries}, set(Catalog.load().names()))
        self.assertEqual(len(entries), 54)
        for entry in entries:
            asset = paths.ASSETS_DIR / entry["file"]
            self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), entry["sha256"])
            self.assertTrue(entry["source_page"].startswith("https://"))
            self.assertGreaterEqual(min(entry["width"], entry["height"]), 100)

    def test_windows_icon_contains_small_and_hidpi_sizes(self):
        payload = paths.asset("icons", "app.ico").read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", payload)
        self.assertEqual((reserved, kind), (0, 1))
        widths = {payload[6 + index * 16] or 256 for index in range(count)}
        self.assertTrue({16, 20, 24, 32, 48, 64, 128, 256} <= widths)

    def test_english_names_are_complete_and_do_not_change_storage_keys(self):
        previous = get_language()
        try:
            catalog = Catalog.load()
            original_names = catalog.names()
            set_language("en_US")
            for character in catalog:
                self.assertTrue(character.name_en, character.name)
                self.assertTrue(character_name(character.name).replace(" · ", " - ").isascii(), character.name)
            self.assertEqual(character_name("里芙-狂猎"), "Lyfe · Wild Hunt")
            self.assertEqual(armor_name("凯茜娅-狂诗"), "Rhapsody")
            self.assertEqual(element_name("低温"), "Frost")
            self.assertEqual(catalog.names(), original_names)
            set_language("zh_CN")
            self.assertEqual(character_name("里芙-狂猎"), "里芙 · 狂猎")
        finally:
            set_language(previous)

    def test_translation_keys_and_format_placeholders_match(self):
        import string
        self.assertEqual(set(TRANSLATIONS["zh_CN"]), set(TRANSLATIONS["en_US"]))
        formatter = string.Formatter()
        for key, text in TRANSLATIONS["zh_CN"].items():
            fields = {field for _literal, field, _spec, _conv in formatter.parse(text) if field}
            translated = TRANSLATIONS["en_US"][key]
            translated_fields = {field for _literal, field, _spec, _conv in formatter.parse(translated) if field}
            self.assertEqual(fields, translated_fields, key)
