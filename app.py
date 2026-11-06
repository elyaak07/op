"""Motor OP Studio V1.4 — un écran, import Excel/MOP unifié et automatique.

Changer ici le nombre de caractères supprimés dans le TITRE du graphique.
L'extension .xlsx/.xlsm ne compte pas dans les caractères à supprimer.
"""
from __future__ import annotations

import hashlib
import json
import re

import streamlit as st

from charts import build_combined, render_png
from core import (
    METRICS, SHEET_NAME, display_factor, interp, make_project,
    new_point, new_segment, visible_metrics,
)
from loader import load_document

# ================= RÉGLAGES PERSONNALISABLES =================
TITLE_REMOVE_FIRST = 0       # caractères retirés au début du nom Excel
TITLE_REMOVE_LAST = 0        # caractères retirés à la fin du nom Excel
# ============================================================

st.set_page_config(page_title='Motor OP Studio', page_icon='📈', layout='wide',
                   initial_sidebar_state='collapsed')
st.markdown('''<style>
/* Interface compacte ; toutes les actions essentielles restent sur un écran. */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none!important;}
[data-testid="stHeader"] {height: 1.6rem; background: transparent;}
[data-testid="stAppViewContainer"] .block-container {
  max-width: 100vw; padding: .30rem 1.0rem .50rem; }
[data-testid="stVerticalBlock"] { gap: .35rem; }
[data-testid="stHorizontalBlock"] { gap: .50rem; }
[data-testid="stFileUploaderDropzone"] {padding: .30rem .60rem; min-height:3.2rem;}
[data-testid="stFileUploaderDropzoneInstructions"] {line-height:1rem;}
[data-testid="stFileUploaderDropzoneInstructions"] small {display:none;}
[data-testid="stFileUploader"] section {margin:0;}
[data-testid="stPlotlyChart"] {margin-top:-.25rem;}
[data-testid="stWidgetLabel"] p {font-size:.82rem;}
[data-testid="stMarkdownContainer"] p {margin-bottom:.1rem;}
button[kind="secondary"], button[kind="primary"] {min-height:2.15rem;}
.op-brand {font-weight:800; font-size:1.30rem; letter-spacing:-.04rem;}
.op-brand small {font-size:.76rem; font-weight:500; color:#7c8798; letter-spacing:0;}
@media (max-height: 820px) {
 [data-testid="stAppViewContainer"] .block-container {padding-top:0;}
 [data-testid="stVerticalBlock"] {gap:.18rem;}
}
</style>''', unsafe_allow_html=True)


def initialize() -> None:
    defaults = {
        'source_token': None, 'source_excel': None, 'source_filename': '',
        'source_data': None, 'source_stats': None, 'annotations': [],
        'settings': None, 'source_kind': '', 'load_error': None,
        'failed_token': None, 'upload_rev': 0, 'load_epoch': 0,
        'plot_epoch': 0, 'pending': None, 'mode_prev': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def import_file(payload: dict, token: str) -> None:
    """Applique un projet en bloc, une seule fois après dépôt/import."""
    state = st.session_state
    state.source_token = token
    state.source_excel = payload['excel_bytes']
    state.source_filename = payload['excel_filename']
    state.source_data = payload['data']
    state.source_stats = payload['stats']
    state.annotations = payload['annotations']
    state.settings = payload['settings']
    state.source_kind = payload['document_type']
    state.load_error = None
    state.failed_token = None
    state.pending = None
    state.mode_prev = None
    state.plot_epoch += 1
    state.load_epoch += 1


def close_file() -> None:
    state = st.session_state
    state.source_token = None
    state.source_excel = None
    state.source_filename = ''
    state.source_data = None
    state.source_stats = None
    state.annotations = []
    state.settings = None
    state.source_kind = ''
    state.load_error = None
    state.failed_token = None
    state.pending = None
    state.mode_prev = None
    state.plot_epoch += 1
    state.load_epoch += 1
    # Un nouveau widget de dépôt garantit qu'un ancien fichier n'est pas rechargé.
    state.upload_rev += 1


def annotation_label(ann: dict) -> str:
    label = ann.get('label') or ('Point' if ann['type'] == 'point' else 'Segment')
    return f"{label} · {METRICS[ann['metric']]['unit']} · {ann['id'][-5:]}"


def safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', title).strip(' ._')[:95]
    return name or 'motor_op'


@st.cache_data(max_entries=12, show_spinner=False)
def cached_png(data_json: str, ann_json: str, settings_json: str) -> bytes:
    return render_png(json.loads(data_json), json.loads(ann_json), json.loads(settings_json))


@st.cache_data(max_entries=8, show_spinner=False)
def cached_mop(source_token: str, filename: str, ann_json: str,
               settings_json: str, _source_excel: bytes) -> bytes:
    return make_project(_source_excel, filename, json.loads(ann_json), json.loads(settings_json))


@st.dialog('Réglages du graphique')
def settings_dialog():
    s = st.session_state.settings
    ep = st.session_state.load_epoch
    with st.form(f'settings_form_{ep}'):
        theme = st.selectbox('Thème', ('Clair', 'Sombre'),
                             index=0 if s['theme'] == 'Clair' else 1)
        markers = st.checkbox('Points de mesure visibles', value=s['markers'])
        line_width = st.slider('Épaisseur des courbes', 1.0, 6.0, float(s['line_width']), .25)
        eff_modes = ['Auto', 'Valeurs en %', 'Valeurs 0–1']
        efficiency = st.selectbox('Format de rendement', eff_modes,
                                   index=eff_modes.index(s['efficiency_mode']))
        height = st.slider('Hauteur graphique (px)', 330, 750, int(s['chart_height']), 10)
        if st.form_submit_button('Appliquer', type='primary', use_container_width=True):
            s.update(theme=theme, markers=markers, line_width=line_width,
                     efficiency_mode=efficiency, chart_height=height)
            st.session_state.plot_epoch += 1
            st.rerun()


@st.dialog('Nouvelle annotation')
def new_annotation_dialog(metric: str):
    data = st.session_state.source_data
    settings = st.session_state.settings
    factor = display_factor(metric, data, settings)
    unit = METRICS[metric]['unit']
    st.caption(f"Grandeur : {METRICS[metric]['name']}")
    with st.form('add_annotation_form'):
        kind = st.radio('Type', ['Point', 'Segment'], horizontal=True)
        auto_y = st.checkbox('Ordonnée Y calculée par interpolation', value=False)
        c0, c1 = st.columns(2)
        with c0:
            x0 = st.number_input('RPM départ', value=float(min(data['rpm'])), format='%.2f')
        with c1:
            y0 = st.number_input(f'Y départ [{unit}]', value=0.0, format='%.3f', disabled=auto_y)
        x1 = y1 = None
        if kind == 'Segment':
            c2, c3 = st.columns(2)
            with c2:
                x1 = st.number_input('RPM fin', value=float(max(data['rpm'])), format='%.2f')
            with c3:
                y1 = st.number_input(f'Y fin [{unit}]', value=0.0, format='%.3f', disabled=auto_y)
        label = st.text_input('Étiquette (facultative)', max_chars=100)
        color = st.color_picker('Couleur', '#E11D48')
        if st.form_submit_button('Ajouter', type='primary', use_container_width=True):
            a = interp(data, metric, x0) if auto_y else y0 / factor
            b = (interp(data, metric, x1) if auto_y else y1 / factor) if kind == 'Segment' else None
            if a is None or (kind == 'Segment' and b is None):
                st.error('Interpolation impossible hors de la plage de données.')
            else:
                if kind == 'Point':
                    st.session_state.annotations.append(new_point(metric, x0, a, label, color))
                else:
                    st.session_state.annotations.append(new_segment(metric, x0, a, x1, b, label, color))
                st.session_state.plot_epoch += 1
                st.rerun()


@st.dialog('Modifier une annotation')
def edit_annotation_dialog(ann_id: str):
    ann = next((a for a in st.session_state.annotations if a['id'] == ann_id), None)
    if ann is None:
        st.warning('Annotation introuvable.')
        return
    data, settings = st.session_state.source_data, st.session_state.settings
    factor = display_factor(ann['metric'], data, settings)
    unit = METRICS[ann['metric']]['unit']
    with st.form(f'edit_{ann_id}'):
        label = st.text_input('Étiquette', value=ann['label'], max_chars=100)
        color = st.color_picker('Couleur', ann['color'])
        if ann['type'] == 'point':
            px = st.number_input('RPM', value=float(ann['x']), format='%.3f')
            py = st.number_input(f'Y [{unit}]', value=float(ann['y'] * factor), format='%.5f')
        else:
            px0 = st.number_input('RPM début', value=float(ann['x0']), format='%.3f')
            py0 = st.number_input(f'Y début [{unit}]', value=float(ann['y0'] * factor), format='%.5f')
            px1 = st.number_input('RPM fin', value=float(ann['x1']), format='%.3f')
            py1 = st.number_input(f'Y fin [{unit}]', value=float(ann['y1'] * factor), format='%.5f')
        if st.form_submit_button('Enregistrer', type='primary', use_container_width=True):
            ann.update(label=label, color=color)
            if ann['type'] == 'point':
                ann.update(x=px, y=py / factor)
            else:
                ann.update(x0=px0, y0=py0 / factor, x1=px1, y1=py1 / factor)
            st.session_state.plot_epoch += 1
            st.rerun()


initialize()

# ================= IMPORT UNIQUE, DIRECT ET PERMANENT =================
logo, drop, manage = st.columns([2.3, 5.3, 1.5], vertical_alignment='center')
with logo:
    st.markdown('<div class="op-brand">Motor OP Studio <small>V1.4</small></div>',
                unsafe_allow_html=True)
    st.caption('Characteristics Nom OP · 4 axes indépendants')
with drop:
    uploaded = st.file_uploader(
        'Déposez ici un Excel (.xlsx/.xlsm) ou un projet (.mop), ou cliquez pour parcourir',
        type=['xlsx', 'xlsm', 'mop'], accept_multiple_files=False,
        key=f"import_{st.session_state.upload_rev}",
        help='Un seul import, ouverture automatique du format détecté.',
    )
with manage:
    if st.session_state.source_data is not None:
        if st.button('Fermer le fichier', use_container_width=True):
            close_file()
            st.rerun()
    else:
        st.caption('Glisser-déposer ou clic')

if uploaded is not None:
    raw = uploaded.getvalue()
    token = f"{uploaded.name}:{hashlib.sha256(raw).hexdigest()}"
    if token != st.session_state.source_token and token != st.session_state.failed_token:
        try:
            with st.spinner('Ouverture automatique…'):
                payload = load_document(raw, uploaded.name,
                                        TITLE_REMOVE_FIRST, TITLE_REMOVE_LAST)
            import_file(payload, token)
            st.rerun()  # Affiche immédiatement le nouveau graphique, sans second clic.
        except Exception as exc:
            st.session_state.failed_token = token
            st.session_state.load_error = str(exc)

if st.session_state.load_error:
    st.error(f"Import impossible : {st.session_state.load_error}")

if st.session_state.source_data is None:
    st.info('Dépose un classeur Excel comportant la feuille « Characteristics Nom OP » '
            'ou un projet `.mop`. Le graphique s’affichera automatiquement ici.')
    st.caption('Lecture automatique : B = courant, C = couple, D = puissance, '
               'E = RPM, F = rendement ; début ligne 3, arrêt au premier B vide.')
    st.stop()

s = st.session_state.settings
data = st.session_state.source_data
anns = st.session_state.annotations
ep = st.session_state.load_epoch

# ================= COMMANDES PERMANENTES =================
bar = st.columns([3.1, 1, 1, 1, 1, 1.12, 1.22, .88], vertical_alignment='bottom')
with bar[0]:
    s['chart_title'] = st.text_input('Titre du graphique', value=s['chart_title'],
                                      key=f'title_{ep}', max_chars=160)
for col, (metric, entry) in zip(bar[1:5], METRICS.items()):
    with col:
        s['visible'][metric] = st.checkbox(entry['axis_title'],
                                           value=s['visible'][metric],
                                           key=f'visible_{ep}_{metric}')

# Les exports sont calculés depuis l'état des widgets de CE rerun, sans attendre
# un second clic. on_click='ignore' évite un rerun parasite après téléchargement.
serialized_data = json.dumps(data, ensure_ascii=False)
serialized_anns = json.dumps(anns, ensure_ascii=False, sort_keys=True)
serialized_settings = json.dumps(s, ensure_ascii=False, sort_keys=True)
with bar[5]:
    st.download_button('Télécharger PNG',
                       data=cached_png(serialized_data, serialized_anns, serialized_settings),
                       file_name=f"{safe_filename(s['chart_title'])}.png",
                       mime='image/png', on_click='ignore',
                       use_container_width=True)
with bar[6]:
    st.download_button('Sauver .mop',
                       data=cached_mop(st.session_state.source_token,
                                       st.session_state.source_filename,
                                       serialized_anns, serialized_settings,
                                       st.session_state.source_excel),
                       file_name=f"{safe_filename(s['chart_title'])}.mop",
                       mime='application/octet-stream', on_click='ignore',
                       use_container_width=True)
with bar[7]:
    if st.button('Réglages', use_container_width=True):
        settings_dialog()

# ================= FIGURE ET ANNOTATIONS =================
graph_col, tools_col = st.columns([4.5, 1.35], gap='small', vertical_alignment='top')
keys = visible_metrics(s)
with tools_col:
    st.markdown('**Annotations**')
    if keys:
        metric = st.selectbox('Grandeur pour annotation', keys,
                              format_func=lambda k: METRICS[k]['name'],
                              key=f'metric_{ep}', label_visibility='collapsed')
        mode = st.radio('Mode', ['Explorer', 'Point', 'Segment'],
                        horizontal=True, key=f'mode_{ep}', label_visibility='collapsed')
        if st.session_state.mode_prev != (metric, mode):
            st.session_state.pending = None
            st.session_state.mode_prev = (metric, mode)
            st.session_state.plot_epoch += 1

        if mode == 'Explorer':
            st.caption('Zoom, survol et déplacement du graphique.')
        elif mode == 'Point':
            st.caption('Clique sur un point de mesure, ou encadre-le avec la sélection.')
        else:
            if st.session_state.pending:
                p = st.session_state.pending
                st.caption(f"Début : {p['x']:.1f} RPM. Sélectionne le second point.")
                if st.button('Annuler le début', use_container_width=True):
                    st.session_state.pending = None
                    st.session_state.plot_epoch += 1
                    st.rerun()
            else:
                st.caption('Clique successivement sur deux points pour créer un segment.')
        if st.button('＋ Annotation manuelle', use_container_width=True):
            new_annotation_dialog(metric)
    else:
        metric, mode = None, 'Explorer'
        st.caption('Coche une courbe pour ajouter une annotation.')

    if anns:
        st.markdown(f'**Existantes ({len(anns)})**')
        options = {a['id']: a for a in anns}
        ann_id = st.selectbox('Annotation', list(options.keys()),
                               format_func=lambda a: annotation_label(options[a]),
                               label_visibility='collapsed', key=f'annotation_{ep}')
        edit, delete = st.columns(2)
        with edit:
            if st.button('Modifier', use_container_width=True):
                edit_annotation_dialog(ann_id)
        with delete:
            if st.button('Supprimer', use_container_width=True):
                st.session_state.annotations = [a for a in anns if a['id'] != ann_id]
                st.session_state.plot_epoch += 1
                st.rerun()

with graph_col:
    fig, trace_map = build_combined(
        data, anns, s,
        edit_metric=metric if mode in ('Point', 'Segment') else None,
        pending=st.session_state.pending, chart_height=int(s['chart_height']))
    plot_key = f"plot_{ep}_{st.session_state.plot_epoch}"
    config = {'displaylogo': False, 'responsive': True, 'scrollZoom': True,
              'modeBarButtonsToRemove': ['lasso2d']}
    if metric and mode in ('Point', 'Segment'):
        event = st.plotly_chart(fig, on_select='rerun', selection_mode=['box', 'points'],
                                key=plot_key, use_container_width=True, config=config)
        hits = [p for p in event.selection.points
                if p.get('curve_number') == trace_map.get(metric)]
        if hits:
            hit = hits[-1]
            x = float(hit['x'])
            y = float(hit['y']) / display_factor(metric, data, s)
            if mode == 'Point':
                anns.append(new_point(metric, x, y))
            elif st.session_state.pending is None:
                st.session_state.pending = {'metric': metric, 'x': x, 'y': y}
            else:
                start = st.session_state.pending
                anns.append(new_segment(metric, start['x'], start['y'], x, y))
                st.session_state.pending = None
            st.session_state.plot_epoch += 1  # évite un doublon sur rerun
            st.rerun()
    else:
        st.plotly_chart(fig, key=plot_key, use_container_width=True, config=config)
    stats = st.session_state.source_stats
    st.caption(f"Source : {st.session_state.source_filename} · "
               f"{stats['rows_kept']} points · {len(anns)} annotation(s) · "
               f"feuille « {SHEET_NAME} »")
