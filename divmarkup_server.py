# divmarkup_server.py
# Local web workbench for divinatory markup — the GUI successor to divmarkup_MAIN.
#
# Serves divmarkup_web/{index.html, style.css, app.js} and a JSON API that wraps
# the existing modules unchanged:
#   MarkupManager, tag_substring      (divmarkup_markup_functions)
#   selectedSynsetManager             (divmarkup_wordnet_functions)
#   AskClaude                         (divmarkup_ask_claude)
#
# Usage:
#   python divmarkup_server.py path/to/text.xml
#   python divmarkup_server.py            (falls back to a file-picker dialog)
# Then open http://127.0.0.1:5757 (opens automatically).
#
# API summary (all JSON):
#   GET  /api/state                    file, totals, resume index, status string
#   GET  /api/sentence/<i>             sentence payload + context + live senses
#   POST /api/word                     {index, word}        add word (spellchecked)
#   POST /api/word/delete              {index, word}
#   POST /api/toggle                   {index, synset, selected}
#   POST /api/synonyms                 {word}               noun synonyms
#   POST /api/add_synset               {index, synset}      add one synset by id
#   POST /api/claude/apodosis          {index}              span suggestion
#   POST /api/claude/synsets           {index, apodosis}    sense suggestions
#   POST /api/commit                   {index, start, end}  tag + autosave
#   POST /api/undo                     restore last committed sentence
#   POST /api/write                    write a dated non-autosave copy

import os
import re
import sys
import webbrowser
from threading import Timer

from flask import Flask, jsonify, request, send_from_directory

from divmarkup_markup_functions import MarkupManager, tag_substring
from divmarkup_wordnet_functions import (
    selectedSynsetManager,
    safe_wn_synset,
    most_primary_sense_lemmas_for,
)
from divmarkup_ask_claude import AskClaude
from file_functions import select_file
from nltk.corpus import wordnet as wn

PORT = 5757
KINDS = ('prognosis', 'gnome', 'counsel')   # reviewed span kinds; absence = unreviewed
CONTEXT_SIZE = 3      # dimmed context sentences shown on each side
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'divmarkup_web')

POLICY_RE = re.compile(r'<policy\s+([^>]*?)>(.*?)</policy>', re.DOTALL)
CANON_RE = re.compile(r'<canon\s+formula="([^"]*)"\s+wn_only="([^"]*)"\s*/?>')
ATTR_RE = re.compile(r'([a-z_-]+)="([^"]*)"')

SEGMENT_RE = re.compile(
    r'<(protasis|apodosis)\s+wn_only="(.*?)"(?:\s+kind="([a-z]*)")?\s*>(.*?)</\1>',
    re.DOTALL,
)


# ================================================================ text helpers
# The first two mirror divmarkup_MAIN so remaining-text behavior is identical.

def get_unmarked_portion(text):
    """Everything after the last </apodosis>; the whole text if untagged."""
    last_close = text.rfind('</apodosis>')
    if last_close == -1:
        return text
    return text[last_close + len('</apodosis>'):]


def has_meaningful_content(text):
    """True if anything besides whitespace and common punctuation remains."""
    return len(re.sub(r'[\s.,;:!?\'"]+', '', text)) > 0


def synset_definition(synset_id):
    try:
        return wn.synset(synset_id).definition()
    except Exception:
        return '(not found in WordNet)'


def segment_sentence(text):
    """Raw sentence text → renderable segments.
    [{kind:'plain'|'marked', text, [tag], [synsets]}] in document order."""
    segments, pos = [], 0
    for m in SEGMENT_RE.finditer(text):
        if m.start() > pos:
            segments.append({'kind': 'plain', 'text': text[pos:m.start()]})
        segments.append({
            'kind': 'marked',
            'tag': m.group(1),
            'synsets': [s.strip() for s in m.group(2).split(',') if s.strip()],
            'span_kind': m.group(3) or None,     # None = never reviewed
            'text': m.group(4),
        })
        pos = m.end()
    if pos < len(text):
        segments.append({'kind': 'plain', 'text': text[pos:]})
    return segments


def marked_detail(text):
    """Committed spans with resolved definitions, for the Committed panel."""
    return [{
        'tag': m.group(1),
        'text': m.group(4),
        'span_kind': m.group(3) or None,         # None = never reviewed
        'synsets': [{'id': sid, 'definition': synset_definition(sid)}
                    for sid in (s.strip() for s in m.group(2).split(','))
                    if sid],
    } for m in SEGMENT_RE.finditer(text)]


def parse_policies(text):
    """Machine-readable policy hooks from the document's annotation_policy
    block. 'applies' lists surface substrings that trigger a governance note
    at tagging time; <canon> lines map recurring formulas to canonical
    senses."""
    policies = []
    for m in POLICY_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        policies.append({
            'id': attrs.get('id', '?'),
            'status': attrs.get('status', ''),
            'applies': [s.strip().lower() for s in attrs.get('applies', '').split(',') if s.strip()],
            'text': m.group(2).strip(),
        })
    canons = [{
        'formula': f.strip().lower(),
        'synsets': [s.strip() for s in ids.split(',') if s.strip()],
    } for f, ids in CANON_RE.findall(text)]
    return policies, canons


def sentence_status(sentence):
    """One char per sentence, driving the progress strip and phase logic.
      d done · p partially marked · t to do · m structural markup · e empty

    Note: split_into_sentences sets parse=False on ANY line containing markup,
    including sentences already bearing <apodosis> tags — which is why the CLI
    skips partially marked sentences after a reload. Checking for apodosis
    tags *before* deferring to the parse flag is what makes them recoverable
    here."""
    text = sentence['text']
    if '<apodosis' in text:
        return 'p' if has_meaningful_content(get_unmarked_portion(text)) else 'd'
    if not sentence['parse']:
        return 'm'
    return 't' if has_meaningful_content(text) else 'e'


# ================================================================ app state
app = Flask(__name__, static_folder=None)

markup_manager = None        # MarkupManager — the file being annotated
ask_claude = None            # AskClaude — suggestion endpoints
synset_manager = None        # selectedSynsetManager for the sentence in progress
synset_manager_index = None  # which sentence that session belongs to
undo_stack = []              # [(index, previous_text)], most recent last
app_policies = []            # parsed from the document's annotation_policy block
app_canons = []


def fresh_synset_session(index):
    global synset_manager, synset_manager_index
    synset_manager = selectedSynsetManager()
    synset_manager_index = index
    return synset_manager


def session_for(index):
    """The live synset session for a sentence; resets if the frontend moved."""
    if synset_manager is None or synset_manager_index != index:
        fresh_synset_session(index)
    return synset_manager


def serialize_senses(manager):
    """selectedSynsetManager.wordnet_data → JSON, insertion order preserved."""
    return [{
        'word': word,
        'senses': [{'id': sid,
                    'definition': synset_definition(sid),
                    'selected': bool(info['selected'])}
                   for sid, info in synsets.items()],
    } for word, synsets in manager.wordnet_data.items()]


def sentence_payload(i, senses=None):
    """The common shape the frontend ingests after fetch, commit, and undo."""
    s = markup_manager.get_sentence(i)
    unmarked = get_unmarked_portion(s['text'])
    return {
        'index': i,
        'parse': s['parse'],
        'segments': segment_sentence(s['text']),
        'marked': marked_detail(s['text']),
        'unmarked': unmarked,
        'meaningful': has_meaningful_content(unmarked),
        'status': sentence_status(s),
        'senses': serialize_senses(session_for(i)) if senses is None else senses,
    }


def context_payload(rng):
    return [{
        'index': j,
        'parse': markup_manager.get_sentence(j)['parse'],
        'segments': segment_sentence(markup_manager.get_sentence(j)['text']),
    } for j in rng]


def body(*keys):
    """Required fields from the JSON request body."""
    data = request.get_json(force=True)
    return [data[k] for k in keys] if len(keys) > 1 else data[keys[0]]


# ================================================================ pages/assets
@app.route('/')
def index_page():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route("/<any('style.css','app.js'):asset>")
def assets(asset):
    return send_from_directory(WEB_DIR, asset)


# ================================================================ api: reading
@app.route('/api/state')
def api_state():
    total = markup_manager.get_total_sentences()
    statuses = ''.join(
        sentence_status(markup_manager.get_sentence(i)) for i in range(total)
    )
    resume = markup_manager.find_last_marked_sentence()
    if resume > 0:
        resume += 1
    while resume < total and statuses[resume] in 'med':
        resume += 1
    return jsonify({
        'file': os.path.basename(markup_manager.source_path),
        'autosave_file': markup_manager.autosave_filename,
        'total': total,
        'resume': min(resume, total - 1),
        'statuses': statuses,
        'claude_available': ask_claude.client is not None,
        'policies': app_policies,
        'canons': app_canons,
    })


@app.route('/api/sentence/<int:i>')
def api_sentence(i):
    total = markup_manager.get_total_sentences()
    if not (0 <= i < total):
        return jsonify({'error': f'index {i} out of range 0–{total - 1}'}), 400
    payload = sentence_payload(i)
    payload['context_before'] = context_payload(range(max(0, i - CONTEXT_SIZE), i))
    payload['context_after'] = context_payload(range(i + 1, min(total, i + 1 + CONTEXT_SIZE)))
    return jsonify(payload)


# ================================================================ api: senses
@app.route('/api/word', methods=['POST'])
def api_add_word():
    i, word = body('index', 'word')
    word = word.strip().lower()
    if not word:
        return jsonify({'error': 'Type a word to add.'}), 400
    mgr = session_for(i)
    checked = mgr.check_spelling(word)      # corrected word, or None
    if checked is None:
        return jsonify({
            'senses': serialize_senses(mgr),
            'message': f'No noun senses found for “{word}”, and no spelling fix helped.',
        })
    mgr.add_word_with_synsets(checked)
    return jsonify({
        'senses': serialize_senses(mgr),
        'message': None if checked == word else f'“{word}” → “{checked}”',
    })


@app.route('/api/word/delete', methods=['POST'])
def api_delete_word():
    i, word = body('index', 'word')
    mgr = session_for(i)
    mgr.delete_word(word)
    return jsonify({'senses': serialize_senses(mgr)})


@app.route('/api/toggle', methods=['POST'])
def api_toggle():
    i, synset, selected = body('index', 'synset', 'selected')
    mgr = session_for(i)
    mgr.set_synset_selection(synset, bool(selected))
    return jsonify({'senses': serialize_senses(mgr)})


@app.route('/api/synonyms', methods=['POST'])
def api_synonyms():
    word = body('word')
    synonyms = {lemma.name().replace('_', ' ')
                for synset in wn.synsets(word, pos=wn.NOUN)
                for lemma in synset.lemmas()
                if lemma.name() != word}
    return jsonify({'word': word, 'synonyms': sorted(synonyms)})


def seed_synset(mgr, synset_id):
    """Put one synset id on the board, selected, under its word(s).
    Returns True on success, False for ids WordNet doesn't know."""
    if not safe_wn_synset(synset_id):
        return False
    if any(synset_id in synsets for synsets in mgr.wordnet_data.values()):
        mgr.set_synset_selection(synset_id, True)
        return True
    for word in most_primary_sense_lemmas_for(synset_id):
        if word in mgr.wordnet_data:
            mgr.set_synset_selection(synset_id, True)
        else:
            mgr.add_word_with_synsets(word, [synset_id])
    return True


@app.route('/api/add_synset', methods=['POST'])
def api_add_synset():
    """Add one specific synset id (from a Claude suggestion or canon chip)."""
    i, synset_id = body('index', 'synset')
    mgr = session_for(i)
    if not seed_synset(mgr, synset_id):
        return jsonify({
            'senses': serialize_senses(mgr),
            'message': f'“{synset_id}” is not a valid WordNet noun synset.',
        })
    return jsonify({'senses': serialize_senses(mgr)})


# ================================================================ api: claude
@app.route('/api/claude/apodosis', methods=['POST'])
def api_claude_apodosis():
    i = body('index')
    unmarked = get_unmarked_portion(markup_manager.get_sentence(i)['text'])
    result = ask_claude.recommend_apodosis(unmarked)
    if result == ask_claude.no_gpt_error_message() or not isinstance(result, dict):
        return jsonify({'error': 'Claude isn’t responding. Select the span by hand.'})
    suggested = result.get('apodosis', '')
    start = unmarked.find(suggested)
    if start == -1:
        return jsonify({
            'error': 'Claude suggested a span that isn’t in the sentence verbatim.',
            'suggested': suggested,
        })
    return jsonify({'start': start, 'end': start + len(suggested), 'text': suggested})


@app.route('/api/claude/synsets', methods=['POST'])
def api_claude_synsets():
    i, apodosis = body('index', 'apodosis')
    mgr = session_for(i)
    suggestions = ask_claude.recommend_synsets(apodosis)
    if suggestions == ask_claude.no_gpt_error_message() or not isinstance(suggestions, list):
        return jsonify({'error': 'Claude isn’t responding.'})
    current = {sid for synsets in mgr.wordnet_data.values() for sid in synsets}
    fresh, known, invalid = [], [], []
    for sid in suggestions:
        if sid in current:
            known.append(sid)
        elif safe_wn_synset(sid):
            fresh.append({'id': sid, 'definition': synset_definition(sid)})
        else:
            invalid.append(sid)
    return jsonify({'fresh': fresh, 'known': known, 'invalid': invalid})


# ================================================================ api: writing
@app.route('/api/commit', methods=['POST'])
def api_commit():
    i, start, end = body('index', 'start', 'end')
    kind = (request.get_json(force=True).get('kind') or 'prognosis')
    if kind not in KINDS:
        return jsonify({'error': f'Unknown kind “{kind}”.'}), 400
    mgr = session_for(i)

    synset_ids = mgr.get_selected_synset_ids()
    if len(synset_ids) == 0:
        return jsonify({'error': 'No senses selected — pick at least one.'}), 400

    full = markup_manager.get_sentence(i)['text']
    unmarked = get_unmarked_portion(full)
    if not (0 <= start < end <= len(unmarked)):
        return jsonify({'error': 'Selection indices out of range — reselect the span.'}), 400

    offset = len(full) - len(unmarked)          # skip past existing markup
    undo_stack.append((i, full))
    markup_manager.set_sentence_text(i, tag_substring(
        full, start + offset, end - start, 'apodosis',
        {'wn_only': synset_ids, 'kind': kind},
    ))
    markup_manager.autosave()
    mgr._save_current_selections_to_memory()
    fresh_synset_session(i)                     # clear the board

    payload = sentence_payload(i, senses=[])
    payload['can_undo'] = True
    return jsonify(payload)


@app.route('/api/edit_span', methods=['POST'])
def api_edit_span():
    """Seed a fresh senses session from the nth committed span, so its
    wn_only list can be edited with the normal tools."""
    i, nth = body('index', 'span')
    full = markup_manager.get_sentence(i)['text']
    matches = list(SEGMENT_RE.finditer(full))
    if not (0 <= nth < len(matches)):
        return jsonify({'error': f'No marked span #{nth} in sentence {i}.'}), 400
    m = matches[nth]
    mgr = fresh_synset_session(i)
    invalid = []
    for sid in (s.strip() for s in m.group(2).split(',')):
        if sid and not seed_synset(mgr, sid):
            invalid.append(sid)
    return jsonify({
        'senses': serialize_senses(mgr),
        'span_text': m.group(4),
        'span_kind': m.group(3) or None,
        'nth': nth,
        'invalid': invalid,
    })


@app.route('/api/rewrite_senses', methods=['POST'])
def api_rewrite_senses():
    """Write the session's selected senses back into the nth span's
    wn_only, preserving its kind. Autosaved and undoable like a commit."""
    i, nth = body('index', 'span')
    mgr = session_for(i)
    synset_ids = mgr.get_selected_synset_ids()
    if len(synset_ids) == 0:
        return jsonify({'error': 'No senses selected — a span needs at least one.'}), 400
    full = markup_manager.get_sentence(i)['text']
    matches = list(SEGMENT_RE.finditer(full))
    if not (0 <= nth < len(matches)):
        return jsonify({'error': f'No marked span #{nth} in sentence {i}.'}), 400
    m = matches[nth]
    kind_attr = f' kind="{m.group(3)}"' if m.group(3) else ''
    rebuilt = (f'<{m.group(1)} wn_only="{synset_ids}"{kind_attr}>'
               f'{m.group(4)}</{m.group(1)}>')
    undo_stack.append((i, full))
    markup_manager.set_sentence_text(i, full[:m.start()] + rebuilt + full[m.end():])
    markup_manager.autosave()
    mgr._save_current_selections_to_memory()
    fresh_synset_session(i)
    payload = sentence_payload(i, senses=[])
    payload['can_undo'] = True
    return jsonify(payload)


@app.route('/api/session/reset', methods=['POST'])
def api_session_reset():
    fresh_synset_session(body('index'))
    return jsonify({'senses': []})


@app.route('/api/set_kind', methods=['POST'])
def api_set_kind():
    """Set the kind attribute on the nth marked span of a sentence —
    the review action for spans committed before kinds existed."""
    i, nth, kind = body('index', 'span', 'kind')
    if kind not in KINDS:
        return jsonify({'error': f'Unknown kind “{kind}”.'}), 400
    full = markup_manager.get_sentence(i)['text']
    matches = list(SEGMENT_RE.finditer(full))
    if not (0 <= nth < len(matches)):
        return jsonify({'error': f'No marked span #{nth} in sentence {i}.'}), 400
    m = matches[nth]
    rebuilt = (f'<{m.group(1)} wn_only="{m.group(2)}" kind="{kind}">'
               f'{m.group(4)}</{m.group(1)}>')
    undo_stack.append((i, full))
    markup_manager.set_sentence_text(i, full[:m.start()] + rebuilt + full[m.end():])
    markup_manager.autosave()
    payload = sentence_payload(i)
    payload['can_undo'] = True
    return jsonify(payload)


@app.route('/api/undo', methods=['POST'])
def api_undo():
    if not undo_stack:
        return jsonify({'error': 'Nothing to undo.'}), 400
    i, previous_text = undo_stack.pop()
    markup_manager.set_sentence_text(i, previous_text)
    markup_manager.autosave()
    fresh_synset_session(i)
    payload = sentence_payload(i)
    payload['can_undo'] = len(undo_stack) > 0
    return jsonify(payload)


@app.route('/api/write', methods=['POST'])
def api_write():
    return jsonify({'file': markup_manager.write_file()})


# ================================================================ start
def main():
    global markup_manager, ask_claude

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        print('Select the file to markup.')
        file_path = select_file()
    if not file_path or not os.path.exists(file_path):
        print('No file selected. Exiting.')
        sys.exit(1)

    global app_policies, app_canons
    markup_manager = MarkupManager(file_path)
    ask_claude = AskClaude()
    app_policies, app_canons = parse_policies(markup_manager.source_text)
    if app_policies:
        print(f'Annotation policies found: {", ".join(p["id"] for p in app_policies)}')

    url = f'http://127.0.0.1:{PORT}'
    print(f'\nDivmarkup workbench: {url}')
    print(f'File: {file_path} — {markup_manager.get_total_sentences()} sentences')
    Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(port=PORT, debug=False)


if __name__ == '__main__':
    main()
