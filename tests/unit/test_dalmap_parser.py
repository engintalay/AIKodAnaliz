"""GELIS9: DALMap XML parser tests."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.routes.project_files import _is_dalmap_file, _parse_dalmap_xml


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DAL-MAPCONFIG>
  <PROXYTABLES>
    <PT name="phhaciz_istek" table="HACIZ_ISTEK" db="EHACIZ" rm="EHACIZ">
      <FIELD id="oid" type="string" column="OID" dbType="char" />
      <FIELD id="vkn" type="string" column="VKN" dbType="char" />
    </PT>
    <PT name="phdurum_kod" table="DURUM_KOD" db="EHACIZ" rm="EHACIZ">
      <FIELD id="kod" type="int" column="KOD" dbType="int" />
    </PT>
  </PROXYTABLES>
  <VIRTUALTABLES>
    <VT name="vhhaciz_istek">
      <PT name="phhaciz_istek" />
    </VT>
    <VT name="vhdurum_kod">
      <PT name="phdurum_kod" />
    </VT>
  </VIRTUALTABLES>
  <CLASSES>
    <CLASS name="tr.gov.example.EHaciz" table="vehaciz" methods="java" numeric_null_value="0">
      <FIELD name="oid" column="oid" primarykey="true" />
      <FIELD name="tutar" column="tutar" primarykey="false" />
    </CLASS>
  </CLASSES>
  <FUNCTIONS />
  <PROCEDURES>
    <SP id="BORC_SORGU" name="BORC_SORGU" db="ehaciz_sp" rm="EHACIZ_mevduat">
      <PARAM id="vkn" type="string" column="vkn" dbType="char" />
    </SP>
  </PROCEDURES>
</DAL-MAPCONFIG>
"""


class TestDalmapParser(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".xml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SAMPLE_XML)

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_is_dalmap_file(self):
        self.assertTrue(_is_dalmap_file("dalMapConfig_EHACIZ.xml"))
        self.assertTrue(_is_dalmap_file("DALMAPCONFIG_X.XML"))
        self.assertFalse(_is_dalmap_file("logback-spring.xml"))
        self.assertFalse(_is_dalmap_file("pom.xml"))

    def test_parse_sections(self):
        result = _parse_dalmap_xml(self.path)
        self.assertEqual(len(result["proxy_tables"]), 2)
        self.assertEqual(len(result["virtual_tables"]), 2)
        self.assertEqual(len(result["classes"]), 1)
        self.assertEqual(len(result["procedures"]), 1)

    def test_proxy_tables_not_polluted_by_vt_refs(self):
        """VT child <PT name=.../> references must not become proxy tables."""
        result = _parse_dalmap_xml(self.path)
        names = [p.get("name") for p in result["proxy_tables"]]
        self.assertEqual(names, ["phhaciz_istek", "phdurum_kod"])
        for pt in result["proxy_tables"]:
            self.assertTrue(pt.get("fields"), f"{pt.get('name')} has no fields")

    def test_virtual_table_mappings(self):
        result = _parse_dalmap_xml(self.path)
        vt = {v["name"]: v for v in result["virtual_tables"]}
        self.assertEqual(vt["vhhaciz_istek"]["proxy_tables"][0]["name"], "phhaciz_istek")

    def test_class_and_procedure_fields(self):
        result = _parse_dalmap_xml(self.path)
        cls = result["classes"][0]
        self.assertEqual(cls["table"], "vehaciz")
        self.assertEqual(len(cls["fields"]), 2)
        sp = result["procedures"][0]
        self.assertEqual(sp["name"], "BORC_SORGU")
        self.assertEqual(len(sp["params"]), 1)

    def test_mappings_built(self):
        result = _parse_dalmap_xml(self.path)
        mappings = result["mappings"]
        self.assertEqual(mappings["classes"][0]["table"], "vehaciz")
        self.assertEqual(mappings["virtual_tables"][0]["proxy_tables"], ["phhaciz_istek"])
        self.assertEqual(mappings["proxy_tables"][0]["table"], "HACIZ_ISTEK")


if __name__ == "__main__":
    unittest.main()
