"""
macOS Contacts integration — searches the AddressBook SQLite databases directly.
Much faster than AppleScript for large contact lists.
"""
import glob
import sqlite3

from flask import Blueprint, jsonify, request

bp = Blueprint('macos_contacts', __name__)

_AB_GLOB = (
    '/Users/*/Library/Application Support/AddressBook/Sources/'
    '*/AddressBook-v22.abcddb'
)

_SEARCH_SQL = '''
    SELECT
        r.ZFIRSTNAME,
        r.ZLASTNAME,
        r.ZNAME,
        r.ZORGANIZATION,
        p.ZFULLNUMBER,
        e.ZADDRESS
    FROM ZABCDRECORD r
    LEFT JOIN ZABCDPHONENUMBER p
        ON p.ZOWNER = r.Z_PK
        AND p.Z_PK = (
            SELECT Z_PK FROM ZABCDPHONENUMBER
            WHERE ZOWNER = r.Z_PK LIMIT 1
        )
    LEFT JOIN ZABCDEMAILADDRESS e
        ON e.ZOWNER = r.Z_PK
        AND e.Z_PK = (
            SELECT Z_PK FROM ZABCDEMAILADDRESS
            WHERE ZOWNER = r.Z_PK LIMIT 1
        )
    WHERE (
        lower(r.ZFIRSTNAME) LIKE ?
        OR lower(r.ZLASTNAME) LIKE ?
        OR lower(r.ZNAME) LIKE ?
    )
    LIMIT 20
'''


def _display_name(first, last, zname, org):
    if first and last:
        return f'{first} {last}'
    if first:
        return first
    if last:
        return last
    if zname:
        return zname
    if org:
        return org
    return ''


@bp.route('/api/macos/contacts/search')
def search_macos_contacts():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'contacts': []})

    pattern = f'%{q.lower()}%'
    seen_names = set()
    contacts = []

    for db_path in glob.glob(_AB_GLOB):
        try:
            conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True,
                                   timeout=3)
            rows = conn.execute(_SEARCH_SQL, (pattern, pattern, pattern)
                                ).fetchall()
            conn.close()
        except Exception:
            continue

        for first, last, zname, org, phone, email in rows:
            name = _display_name(first, last, zname, org)
            if not name:
                continue
            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            contacts.append({
                'name':  name,
                'phone': (phone or '').strip(),
                'email': (email or '').strip(),
            })
            if len(contacts) >= 10:
                break
        if len(contacts) >= 10:
            break

    return jsonify({'contacts': contacts})
