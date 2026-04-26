"""
migrate_to_unified_pipeline.py
-------------------------------
One-time migration: moves serializer_chunks from works.json into
content_pipeline.json, and ensures every pipeline entry has a
serializer_chunks field.

Run once after updating the code:
    python3 migrate_to_unified_pipeline.py

Safe to re-run — it will not overwrite chunks that already exist.
Creates .bak files before modifying anything.
"""
import json
import os
import shutil
from datetime import datetime

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, 'data')

PIPELINE_FILE = os.path.join(DATA_DIR, 'content_pipeline.json')
WORKS_FILE    = os.path.join(DATA_DIR, 'works.json')


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def backup(path):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst   = path + f'.bak_{stamp}'
    shutil.copy2(path, dst)
    print(f'  Backed up {os.path.basename(path)} → {os.path.basename(dst)}')


def main():
    print('\n── Indaba: Unified Pipeline Migration ──\n')

    # ── Load data ─────────────────────────────────────────────────────────────
    pipeline = load(PIPELINE_FILE)
    works_data = load(WORKS_FILE) if os.path.exists(WORKS_FILE) else {'works': []}
    works = works_data.get('works', []) if isinstance(works_data, dict) else []

    print(f'  Pipeline entries : {len(pipeline)}')
    print(f'  Works (serializer): {len(works)}')

    # ── Back up both files ────────────────────────────────────────────────────
    backup(PIPELINE_FILE)
    if works:
        backup(WORKS_FILE)

    # ── Step 1: Ensure every pipeline entry has serializer_chunks ─────────────
    added_field = 0
    for entry in pipeline:
        if 'serializer_chunks' not in entry:
            entry['serializer_chunks'] = []
            added_field += 1

    print(f'\n  Added serializer_chunks field to {added_field} pipeline entries.')

    # ── Step 2: Match works → pipeline entries and migrate chunks ─────────────
    migrated_works   = 0
    unmatched_works  = []

    for work in works:
        chunks = work.get('chunks', [])
        if not chunks:
            continue

        work_title = (work.get('title') or '').lower().strip()
        work_id    = work.get('id', '')

        # Try to find a matching pipeline entry
        match = None

        # Match by book code (work.id == pipeline.book)
        candidates = [e for e in pipeline if e.get('book', '').lower() == work_id.lower()]
        if len(candidates) == 1:
            match = candidates[0]
        elif len(candidates) > 1:
            # Prefer the one whose chapter title is closest to the work title
            for e in candidates:
                if (e.get('chapter') or '').lower().strip() == work_title:
                    match = e
                    break
            if not match:
                match = candidates[0]  # fallback to first

        # Match by chapter title
        if not match:
            for e in pipeline:
                if (e.get('chapter') or '').lower().strip() == work_title:
                    match = e
                    break

        if match:
            # Only migrate if entry has no chunks yet
            if not match.get('serializer_chunks'):
                # Convert works-format chunks to pipeline-format chunks
                new_chunks = []
                for c in chunks:
                    new_chunks.append({
                        'id':               c.get('id', ''),
                        'content':          c.get('content', ''),
                        'cliffhanger_note': c.get('cliffhanger_note', ''),
                        'status':           c.get('status', 'ready'),
                        'word_count':       c.get('word_count', len(c.get('content', '').split())),
                        'created_at':       c.get('created_at', ''),
                        'message_id':       c.get('message_id', None),
                    })
                match['serializer_chunks'] = new_chunks
                migrated_works += 1
                print(f'  Migrated {len(new_chunks)} chunks: "{work.get("title")}" → "{match.get("chapter")}"')
            else:
                print(f'  Skipped (already has chunks): "{work.get("title")}"')
        else:
            unmatched_works.append(work)
            print(f'  WARNING: No pipeline match for work "{work.get("title")}" (id={work_id})')

    # ── Save updated pipeline ─────────────────────────────────────────────────
    save(PIPELINE_FILE, pipeline)
    print(f'\n  Saved updated pipeline ({len(pipeline)} entries).')

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f'\n── Migration complete ──')
    print(f'  Fields added       : {added_field}')
    print(f'  Works migrated     : {migrated_works}')
    print(f'  Unmatched works    : {len(unmatched_works)}')
    if unmatched_works:
        print('\n  Unmatched works (manual review needed):')
        for w in unmatched_works:
            print(f'    - "{w.get("title")}" (id={w.get("id")})')
    print()


if __name__ == '__main__':
    main()
