"""Ouverture d'un Excel ou d'un projet Motor OP Studio par un point d'entrée unique.

Module indépendant de Streamlit, donc testable automatiquement.
"""
from __future__ import annotations

from pathlib import Path

from core import normalize_settings, parse_excel, read_project


def title_from_filename(filename: str, remove_first: int = 0, remove_last: int = 0) -> str:
    """Titre à partir du nom Excel, sans extension, avec troncature explicite."""
    basename = Path(filename.replace('\\', '/').rsplit('/', 1)[-1]).stem
    first = max(0, int(remove_first))
    last = max(0, int(remove_last))
    title = basename[first:]
    if last:
        title = title[:-last]
    return title.strip() or basename or 'Motor characteristics'


def load_document(raw: bytes, filename: str, remove_first: int = 0,
                  remove_last: int = 0) -> dict:
    """Reconnaît automatiquement Excel / .mop, et prépare l'état du projet.

    Ne conserve pas le .mop comme source : il extrait son Excel incorporé.
    Les anciens projets conservent le titre édité, les annotations et les réglages.
    """
    ext = Path(filename).suffix.casefold()
    if ext in ('.xlsx', '.xlsm'):
        excel = raw
        excel_filename = Path(filename).name
        annotations = []
        settings = normalize_settings(None)
        doc_type = 'Excel'
    elif ext == '.mop':
        excel, meta = read_project(raw)
        excel_filename = meta.get('excel_filename') or 'source.xlsx'
        annotations = meta['annotations']
        settings = normalize_settings(meta['settings'])
        doc_type = 'MOP'
    else:
        raise ValueError('Format non accepté. Déposer un fichier .xlsx, .xlsm ou .mop.')

    data, stats = parse_excel(excel)
    if not settings['chart_title']:
        settings['chart_title'] = title_from_filename(
            excel_filename, remove_first, remove_last)
    return {
        'excel_bytes': excel, 'excel_filename': excel_filename,
        'data': data, 'stats': stats, 'annotations': annotations,
        'settings': settings, 'document_type': doc_type,
    }
