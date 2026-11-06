"""Tests sans navigateur de la chaîne d'import, des exports et des projets."""
from __future__ import annotations
import io
import json
import unittest
from pathlib import Path
from PIL import Image

from core import METRICS, SHEET_NAME, make_project, new_point, new_segment, normalize_settings
from charts import build_combined, render_png
from loader import load_document, title_from_filename

ROOT = Path(__file__).parent


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xlsx = (ROOT/'exemple_classeur_multi_feuilles.xlsx').read_bytes()

    def test_title_auto_trimming(self):
        self.assertEqual(title_from_filename('XXX_MOTEUR_2026.xlsx', 4, 5), 'MOTEUR')
        self.assertEqual(title_from_filename('C:\\dossier\\Example.xlsm', 0, 0), 'Example')
        self.assertEqual(title_from_filename('ABC.xlsx', 10, 0), 'ABC')

    def test_excel_import_from_other_worksheets(self):
        doc = load_document(self.xlsx, 'XXX_MOTEUR_2026.xlsx', 4, 5)
        self.assertEqual(doc['document_type'], 'Excel')
        self.assertEqual(doc['settings']['chart_title'], 'MOTEUR')
        self.assertGreater(doc['stats']['rows_kept'], 0)
        self.assertEqual(set(doc['data']), {'rpm', *METRICS})
        self.assertTrue(all(doc['settings']['visible'].values()))

    def test_mop_roundtrip_with_annotations_and_title(self):
        doc = load_document(self.xlsx, 'MoteurA.xlsx')
        annotations = [new_point('torque', 1250, 40, 'A'),
                       new_segment('power', 1000, 5, 3000, 20, 'B')]
        settings = doc['settings']
        settings['chart_title'] = 'Titre personnalisé'
        settings['visible']['current'] = False
        project = make_project(self.xlsx, doc['excel_filename'], annotations, settings)
        new = load_document(project, 'projet.mop', 99, 99)
        self.assertEqual(new['document_type'], 'MOP')
        self.assertEqual(new['excel_filename'], 'MoteurA.xlsx')
        self.assertEqual(new['settings']['chart_title'], 'Titre personnalisé')
        self.assertFalse(new['settings']['visible']['current'])
        self.assertEqual(len(new['annotations']), 2)
        self.assertEqual(new['annotations'][1]['type'], 'segment')

    def test_legacy_mop(self):
        doc = load_document((ROOT/'exemple_projet_annoté.mop').read_bytes(), 'old.mop')
        self.assertTrue(doc['data']['rpm'])
        self.assertTrue(doc['settings']['chart_title'])

    def test_unsupported_format_and_invalid_file(self):
        with self.assertRaisesRegex(ValueError, 'Format non accepté'):
            load_document(b'nope', 'un_fichier.xls')
        with self.assertRaisesRegex(ValueError, 'classeur Excel'):
            load_document(b'not excel', 'fichier.xlsx')

    def test_png_and_plotly_figures(self):
        doc = load_document(self.xlsx, 'test.xlsx')
        data, settings = doc['data'], doc['settings']
        ann = [new_point('torque', 2000, 20, 'Test')]
        fig, traces = build_combined(data, ann, settings, edit_metric='torque', chart_height=440)
        self.assertEqual(len(traces), 4)
        self.assertEqual(fig.layout.title.text, 'test')
        png = render_png(data, ann, settings)
        im = Image.open(io.BytesIO(png))
        self.assertEqual(im.format, 'PNG')
        self.assertGreater(im.width, 1200)
        self.assertGreater(im.height, 650)
        settings['visible']['power'] = False
        fig, traces = build_combined(data, ann, settings)
        self.assertNotIn('power', traces)
        self.assertFalse(fig.layout.yaxis3.visible)
        png = render_png(data, ann, settings)
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))


if __name__ == '__main__':
    unittest.main()
