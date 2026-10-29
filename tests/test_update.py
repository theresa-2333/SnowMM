"""v1.1 regressions: archive staging, skin scope, English paths and migration."""
from __future__ import annotations

import json
import stat
import struct
import zipfile
import zlib
from unittest import mock

import py7zr
import rarfile

from snowmm.core import paths
from snowmm.core.catalog import Catalog
from snowmm.core.models import Mod
from snowmm.core.naming import folder_for
from snowmm.core.skins import skins_for
from snowmm.core.store import Store
from tests.test_core import TempCase
from tools.fetch_skins import parse_skins


class UpdateTests(TempCase):
    character = "凯茜娅-狂诗"

    def source(self, name="Skin_100_P.pak"):
        source = self.tmp / name
        source.write_bytes(b"package")
        return source

    def test_wiki_catalog_has_unique_ids_and_default_for_every_armor(self):
        payload = json.loads(paths.asset("catalog", "skins.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["skins"]), 116)
        for character in Catalog.load():
            skins = skins_for(character.name)
            self.assertEqual(skins[0].id, "default")
            self.assertEqual(len({skin.id for skin in skins}), len(skins))
            self.assertTrue(all(skin.id.isascii() for skin in skins))
        self.assertIn("星抚恋音", [skin.name for skin in skins_for(self.character)])
        self.assertIn("花间蝶踪", [skin.name for skin in skins_for(self.character)])

    def test_wiki_parser_ignores_unknown_characters_and_deduplicates(self):
        heading = '<h3><span>凯茜娅·狂诗丨花间蝶踪「Floral Flutter」</span></h3>'
        rows, unknown = parse_skins(heading * 2 + '<h3>未知·角色|测试「Test」</h3>', {self.character})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "floral-flutter")
        self.assertEqual(unknown, ["未知-角色"])

    def test_import_and_move_between_skins_keep_disabled_package(self):
        source = self.source()
        source.with_suffix(".utoc").write_bytes(b"companion")
        mod = self.manager.import_paths([source], character=self.character).added[0]
        self.manager.set_enabled([mod], False)
        self.assertIsNone(self.manager.move_mod(mod, self.character, "floral-flutter"))
        self.assertEqual(mod.skin, "floral-flutter")
        self.assertEqual(mod.directory, self.mods_dir / folder_for(self.character) / mod.skin)
        self.assertFalse(mod.enabled_path.exists())
        self.assertEqual(len(self.manager.siblings(mod)), 2)
        reloaded = Store(self.store.path).load().mods[0]
        self.assertEqual(reloaded.skin, mod.skin)
        self.assertTrue(reloaded.disabled_path.exists())

    def test_scan_english_paths_restores_character_and_skin(self):
        relative = f"{folder_for(self.character)}/floral-flutter/Test.pak.disabled"
        self.make_pak(relative)
        mod = self.manager.scan_storage(known_characters=Catalog.load().names())[0]
        self.assertEqual((mod.character, mod.skin), (self.character, "floral-flutter"))
        self.assertFalse(mod.enabled)

    def test_different_skins_do_not_conflict_but_same_skin_does(self):
        source = self.source()
        self.manager.import_paths([source], character=self.character)
        self.manager.import_paths([source], character=self.character, skin="floral-flutter")
        self.assertEqual(self.manager.issues(), [])
        self.manager.import_paths([source], character=self.character, skin="floral-flutter")
        issues = self.manager.issues()
        self.assertEqual([issue.kind for issue in issues], ["multi_enabled"])
        self.assertEqual(len(issues[0].mod_ids), 2)

    def test_special_cards_skip_duplicates_but_still_report_missing(self):
        source = self.source()
        for character in ("基地", "杂项"):
            self.assertTrue(Catalog.load().get(character).special)
            self.manager.import_paths([source, self.source("Other.pak")], character=character)
        self.store.add_mod(Mod.from_dict(self.store.mods[0].to_dict() | {"id": "duplicate"}))
        self.assertEqual(self.manager.issues(Catalog.load().names()), [])
        self.store.mods[0].disk_path.unlink()
        self.assertIn("missing_file", [issue.kind for issue in self.manager.issues()])

    def test_invalid_skin_rejected_without_writing(self):
        result = self.manager.import_paths([self.source()], character=self.character, skin="../escape")
        self.assertTrue(result.errors)
        self.assertEqual(list(self.mods_dir.iterdir()), [])

    def test_legacy_record_defaults_to_default_skin(self):
        self.assertEqual(Mod.from_dict({"character": self.character}).skin, "default")

    def test_normalize_is_idempotent_with_collision_and_disabled_companions(self):
        old = self.make_pak(f"{self.character}/外观_100_P.pak.disabled")
        self.make_pak(f"{self.character}/外观_100_P.utoc.disabled")
        mod = self.manager.scan_storage()[0]
        self.manager.import_paths([self.source("外观_100_P.pak")], character=self.character)
        changed, errors = self.manager.normalize_layout(Catalog.load().names())
        self.assertEqual((changed, errors), (1, []))
        self.assertFalse(old.exists())
        self.assertFalse(mod.enabled_path.exists())
        self.assertEqual(len(self.manager.siblings(mod)), 2)
        self.assertTrue(mod.stem.endswith(" (2)_100_P"))
        self.assertTrue(mod.filename.isascii())
        self.assertEqual(mod.directory.name, "katya-rhapsody")
        self.assertTrue(list(self.tmp.glob("data-before-english-*.json")))
        self.assertEqual(self.manager.normalize_layout(Catalog.load().names()), (0, []))
        self.assertTrue(all(mod.exists for mod in Store(self.store.path).load().mods))

    def test_normalize_move_failure_preserves_source_and_record(self):
        old = self.make_pak(f"{self.character}/Old.pak.disabled")
        mod = self.manager.scan_storage()[0]
        with mock.patch("snowmm.core.manager.shutil.move", side_effect=OSError("locked")):
            changed, errors = self.manager.normalize_layout(Catalog.load().names())
        self.assertEqual(changed, 0)
        self.assertTrue(errors)
        self.assertEqual(mod.disk_path, old)
        self.assertTrue(old.exists())

    def test_zip_nested_multi_package_and_companions(self):
        archive = self.tmp / "mods.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            for prefix in ("中文/one", "中文/two"):
                for extension in (".pak", ".utoc", ".ucas", ".sig"):
                    handle.writestr(prefix + extension, extension)
            handle.writestr("readme.txt", "ignore")
            handle.writestr("nested.zip", "ignore nested archives")
        result = self.manager.import_paths([archive], character=self.character, skin="floral-flutter")
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.added), 2)
        self.assertEqual(len(list(result.added[0].directory.iterdir())), 8)
        self.assertTrue(all(len(self.manager.siblings(mod)) == 4 for mod in result.added))
        self.assertTrue(archive.exists())

    def test_7z_nested_unicode_package(self):
        archive = self.tmp / "mods.7z"
        source = self.source("模型_100_P.pak")
        with py7zr.SevenZipFile(archive, "w") as handle:
            handle.write(source, "中文/模型_100_P.pak")
        result = self.manager.import_paths([archive], character=self.character)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.added[0].disk_path.read_bytes(), b"package")

    def test_rar_stored_package(self):
        # Build a minimal RAR3 store archive with our own payload.
        def block(kind, flags, extra=b""):
            body = struct.pack("<BHH", kind, flags, 7 + len(extra)) + extra
            return struct.pack("<H", zlib.crc32(body) & 0xffff) + body

        name, payload = b"nested/Skin.pak", b"rar package"
        header = rarfile.S_FILE_HDR.pack(len(payload), len(payload), 2, zlib.crc32(payload),
                                         0, 20, rarfile.RAR_M0, len(name), 0x20)
        archive = self.tmp / "mods.rar"
        archive.write_bytes(rarfile.RAR_ID + block(rarfile.RAR_BLOCK_MAIN, 0, bytes(6))
                            + block(rarfile.RAR_BLOCK_FILE, rarfile.RAR_LONG_BLOCK, header + name)
                            + payload + block(rarfile.RAR_BLOCK_ENDARC, 0))
        result = self.manager.import_paths([archive], character=self.character)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.added[0].disk_path.read_bytes(), payload)

    def test_unsafe_zip_paths_are_rejected_before_any_import(self):
        for path in ("../escape.pak", "C:/escape.pak", "/escape.pak", "dir\\..\\escape.pak",
                     "dir/CON.pak", "dir/file.pak:evil", "dir./file.pak"):
            with self.subTest(path=path):
                archive = self.tmp / "bad.zip"
                with zipfile.ZipFile(archive, "w") as handle:
                    handle.writestr("good.pak", "good")
                    handle.writestr(path, "bad")
                result = self.manager.import_paths([archive], character=self.character)
                self.assertTrue(result.errors)
                self.assertEqual(result.added, [])
        self.assertEqual(list(self.mods_dir.iterdir()), [])

    def test_zip_link_is_rejected(self):
        archive = self.tmp / "link.zip"
        entry = zipfile.ZipInfo("link.pak")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr(entry, "../../outside")
        result = self.manager.import_paths([archive], character=self.character)
        self.assertTrue(result.errors)
        self.assertEqual(result.added, [])

    def test_corrupt_archive_does_not_block_other_sources(self):
        archive = self.tmp / "broken.zip"
        archive.write_bytes(b"broken")
        result = self.manager.import_paths([archive, self.source()], character=self.character)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.added), 1)

    def test_archive_limit_and_case_collision(self):
        archive = self.tmp / "bad.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("skin.pak", "a")
            handle.writestr("SKIN.pak", "b")
        self.assertTrue(self.manager.import_paths([archive], character=self.character).errors)
        with mock.patch("snowmm.core.archives.MAX_FILES", 1):
            self.assertTrue(self.manager.import_paths([archive], character=self.character).errors)

    def test_all_bundled_asset_paths_are_ascii(self):
        self.assertTrue(all(path.relative_to(paths.ASSETS_DIR).as_posix().isascii()
                            for path in paths.ASSETS_DIR.rglob("*")))

    def test_stale_bubu_portrait_annotation_keeps_bundled_cover(self):
        character = Catalog.load([{"name": "卜卜-小天师", "portrait": "missing/old-cover.png"}]).get("卜卜-小天师")
        self.assertTrue(character.portrait.endswith("bubu-the-geomancer.png"))
        self.assertTrue(paths.ART_DIR.joinpath("thermal/bubu-the-geomancer.png").exists())

    def test_archive_batch_name_is_applied_to_each_package(self):
        archive = self.tmp / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("first.pak", "one")
            handle.writestr("second.pak", "two")
        result = self.manager.import_paths([archive], character=self.character, name="Collection")
        self.assertEqual({mod.name for mod in result.added}, {"Collection · first", "Collection · second"})
