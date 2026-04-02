#!/usr/bin/env python3
"""
Voicing Engine — generates chord progressions with multiple voicing levels.
Handles curriculum progression, key rotation, and ratings-aware generation.
"""

import json
import random
import hashlib
from datetime import date, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional

# ─── Music Theory Core ───────────────────────────────────────────

NOTES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
NOTE_TO_SEMI = {n: i for i, n in enumerate(NOTES)}
# Enharmonic aliases
NOTE_TO_SEMI.update({'C#': 1, 'D#': 3, 'F#': 6, 'G#': 8, 'A#': 10})

KEYS_MAJOR = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
KEYS_MINOR = [k + 'm' for k in KEYS_MAJOR]

# Intervals in semitones
INTERVALS = {
    'R': 0, 'b2': 1, '2': 2, 'b3': 3, '3': 4, '4': 5,
    'b5': 6, '5': 7, '#5': 8, '6': 9, 'b7': 10, '7': 11,
    'b9': 13, '9': 14, '#9': 15, '11': 17, '#11': 18,
    'b13': 20, '13': 21,
}


def note_name(semitone):
    """Convert semitone (0-11) to note name."""
    return NOTES[semitone % 12]


def transpose_note(note, octave, semitones):
    """Transpose a note by semitones, returning (new_note, new_octave)."""
    base = NOTE_TO_SEMI[note] + semitones
    new_oct = octave + base // 12
    new_semi = base % 12
    return NOTES[new_semi], new_oct


def build_chord_notes(root, intervals, base_octave=3):
    """Build chord notes from root and interval list. Returns [(note_name, octave), ...]."""
    root_semi = NOTE_TO_SEMI[root]
    notes = []
    for iv in intervals:
        semi = INTERVALS[iv]
        n, o = transpose_note(root, base_octave, semi)
        notes.append((n, o))
    return notes


def format_note(note, octave):
    """Format as 'C4', 'Bb3', etc."""
    return f"{note}{octave}"


# ─── Chord Quality Definitions ──────────────────────────────────

CHORD_QUALITIES = {
    # Basic triads
    'maj': {'name': 'Major', 'symbol': '', 'intervals': ['R', '3', '5']},
    'min': {'name': 'Minor', 'symbol': 'm', 'intervals': ['R', 'b3', '5']},
    'dim': {'name': 'Diminished', 'symbol': '°', 'intervals': ['R', 'b3', 'b5']},
    'aug': {'name': 'Augmented', 'symbol': '+', 'intervals': ['R', '3', '#5']},

    # 7th chords
    'maj7': {'name': 'Major 7th', 'symbol': 'maj7', 'intervals': ['R', '3', '5', '7']},
    'min7': {'name': 'Minor 7th', 'symbol': 'm7', 'intervals': ['R', 'b3', '5', 'b7']},
    'dom7': {'name': 'Dominant 7th', 'symbol': '7', 'intervals': ['R', '3', '5', 'b7']},
    'min7b5': {'name': 'Half-Diminished', 'symbol': 'ø7', 'intervals': ['R', 'b3', 'b5', 'b7']},
    'dim7': {'name': 'Diminished 7th', 'symbol': '°7', 'intervals': ['R', 'b3', 'b5', '6']},

    # Extended
    'maj9': {'name': 'Major 9th', 'symbol': 'maj9', 'intervals': ['R', '3', '5', '7', '9']},
    'min9': {'name': 'Minor 9th', 'symbol': 'm9', 'intervals': ['R', 'b3', '5', 'b7', '9']},
    'dom9': {'name': 'Dominant 9th', 'symbol': '9', 'intervals': ['R', '3', '5', 'b7', '9']},
    'dom13': {'name': 'Dominant 13th', 'symbol': '13', 'intervals': ['R', '3', 'b7', '9', '13']},

    # Altered
    'dom7alt': {'name': 'Altered Dominant', 'symbol': '7alt', 'intervals': ['R', '3', 'b7', 'b9', '#9', 'b5']},
    'dom7b9': {'name': 'Dominant b9', 'symbol': '7(b9)', 'intervals': ['R', '3', '5', 'b7', 'b9']},
    'dom7sharp9': {'name': 'Dominant #9', 'symbol': '7(#9)', 'intervals': ['R', '3', '5', 'b7', '#9']},
    'dom7sharp11': {'name': 'Dominant #11', 'symbol': '7(#11)', 'intervals': ['R', '3', 'b7', '9', '#11']},
}


# ─── Voicing Strategies ─────────────────────────────────────────

def voicing_root_position(root, quality, octave=3):
    """Basic root position voicing."""
    q = CHORD_QUALITIES[quality]
    notes = build_chord_notes(root, q['intervals'], octave)
    return {
        'name': 'Root Position',
        'level': 'basic',
        'piano_notes': [format_note(n, o) for n, o in notes],
        'description': 'All chord tones stacked from the root',
    }


def voicing_shell(root, quality, octave=3):
    """Shell voicing: root, 3rd, 7th (or 5th for triads)."""
    q = CHORD_QUALITIES[quality]
    ivs = q['intervals']
    if 'b7' in ivs or '7' in ivs:
        shell_ivs = ['R', '3' if '3' in ivs else 'b3', 'b7' if 'b7' in ivs else '7']
    elif 'b3' in ivs:
        shell_ivs = ['R', 'b3', '5' if '5' in ivs else 'b5']
    else:
        shell_ivs = ['R', '3', '5']
    notes = build_chord_notes(root, shell_ivs, octave)
    return {
        'name': 'Shell Voicing',
        'level': 'intermediate',
        'piano_notes': [format_note(n, o) for n, o in notes],
        'description': 'Root + guide tones (3rd & 7th)',
    }


def voicing_drop2(root, quality, octave=3):
    """Drop 2 voicing: take close position, drop 2nd voice down an octave."""
    q = CHORD_QUALITIES[quality]
    ivs = q['intervals'][:4] if len(q['intervals']) >= 4 else q['intervals']
    notes = build_chord_notes(root, ivs, octave)
    if len(notes) >= 4:
        # Drop the 2nd note from top down an octave
        n, o = notes[2]  # 2nd from top in root position (0-indexed: 0,1,2,3 → drop index 2)
        notes[2] = (n, o - 1)
        # Sort by pitch
        notes.sort(key=lambda x: NOTE_TO_SEMI[x[0]] + x[1] * 12)
    return {
        'name': 'Drop 2',
        'level': 'intermediate',
        'piano_notes': [format_note(n, o) for n, o in notes],
        'description': 'Close voicing with 2nd voice dropped an octave — open, spread sound',
    }


def voicing_rootless_a(root, quality, octave=3):
    """Rootless voicing Type A: 3-5-7-9 (or 3-7-9 for simpler chords)."""
    q = CHORD_QUALITIES[quality]
    ivs = q['intervals']
    third = '3' if '3' in ivs else 'b3'
    seventh = 'b7' if 'b7' in ivs else ('7' if '7' in ivs else None)
    if seventh and '9' in INTERVALS:
        voicing_ivs = [third, '5' if '5' in ivs else 'b5', seventh, '9']
    elif seventh:
        voicing_ivs = [third, '5' if '5' in ivs else 'b5', seventh]
    else:
        voicing_ivs = [third, '5']
    # Filter to intervals that exist
    valid_ivs = [iv for iv in voicing_ivs if iv in INTERVALS]
    notes = build_chord_notes(root, valid_ivs, octave)
    return {
        'name': 'Rootless (Type A)',
        'level': 'advanced',
        'piano_notes': [format_note(n, o) for n, o in notes],
        'description': 'No root — 3rd on bottom. Used in ensemble/band context',
    }


def voicing_rootless_b(root, quality, octave=3):
    """Rootless voicing Type B: 7-9-3-5."""
    q = CHORD_QUALITIES[quality]
    ivs = q['intervals']
    third = '3' if '3' in ivs else 'b3'
    seventh = 'b7' if 'b7' in ivs else ('7' if '7' in ivs else None)
    fifth = '5' if '5' in ivs else ('b5' if 'b5' in ivs else '#5')
    if seventh:
        voicing_ivs = [seventh, '9', third, fifth]
        # Put 7th below, then 9 3 5 above
        notes = []
        notes.append(transpose_note(root, octave - 1, INTERVALS[seventh]))
        for iv in ['9', third, fifth]:
            notes.append(transpose_note(root, octave, INTERVALS[iv]))
        return {
            'name': 'Rootless (Type B)',
            'level': 'advanced',
            'piano_notes': [format_note(n, o) for n, o in notes],
            'description': 'No root — 7th on bottom. Inverted rootless voicing',
        }
    return voicing_rootless_a(root, quality, octave)


def voicing_upper_structure(root, quality, octave=3):
    """Upper structure triad over shell."""
    q = CHORD_QUALITIES[quality]
    ivs = q['intervals']
    # Shell in left hand
    third = '3' if '3' in ivs else 'b3'
    seventh = 'b7' if 'b7' in ivs else ('7' if '7' in ivs else '5')
    shell = build_chord_notes(root, [third, seventh], octave)
    # Upper structure: for dom7, use II triad (9, #11, 13)
    if quality.startswith('dom'):
        upper_ivs = ['9', '#11', '13'] if '#11' in ivs else ['9', '5', '13']
        # Fallback if intervals not available
        available = [iv for iv in upper_ivs if iv in INTERVALS]
        if len(available) < 3:
            available = ['9', '5', '13']
    else:
        available = ['9', '5', '13'] if '9' in INTERVALS else ['5', 'R', '3']
    upper = build_chord_notes(root, available, octave + 1)
    all_notes = shell + upper
    all_notes.sort(key=lambda x: NOTE_TO_SEMI[x[0]] + x[1] * 12)
    return {
        'name': 'Upper Structure',
        'level': 'advanced',
        'piano_notes': [format_note(n, o) for n, o in all_notes],
        'description': 'Triad in right hand over guide tones in left — rich, modern sound',
    }


# Map of voicing strategies by level
VOICING_STRATEGIES = {
    'basic': [voicing_root_position],
    'intermediate': [voicing_shell, voicing_drop2],
    'advanced': [voicing_rootless_a, voicing_rootless_b, voicing_upper_structure],
}


def get_voicings_for_chord(root, quality, levels=None, octave=3):
    """Get all voicings for a chord at specified levels."""
    if levels is None:
        levels = ['basic', 'intermediate', 'advanced']
    voicings = []
    for level in levels:
        for fn in VOICING_STRATEGIES.get(level, []):
            v = fn(root, quality, octave)
            v['root'] = root
            v['quality'] = quality
            v['chord_symbol'] = root + CHORD_QUALITIES[quality]['symbol']
            voicings.append(v)
    return voicings


# ─── Guitar Voicings ────────────────────────────────────────────

# Standard tuning: E2 A2 D3 G3 B3 E4 (MIDI: 40 45 50 55 59 64)
GUITAR_TUNING = [40, 45, 50, 55, 59, 64]
GUITAR_STRING_NAMES = ['E', 'A', 'D', 'G', 'B', 'e']

# Pre-defined guitar voicing shapes for common chord types
# Format: list of 6 values (low E to high E), int=fret, 'x'=muted, 0=open
# Each entry: (quality, voicing_name, level, shapes_by_root_string)

GUITAR_VOICINGS = {
    # ─── E-string root shapes ───
    'maj_E': {'frets': [0, 'x', (2, '5'), (1, 'R'), (0, '3'), 0], 'root_string': 0, 'name': 'E Shape', 'level': 'basic'},
    'min_E': {'frets': [0, 'x', (2, '5'), (0, 'b3'), (0, 'b3'), 0], 'root_string': 0, 'name': 'E Shape', 'level': 'basic'},
    'dom7_E': {'frets': [0, 'x', (1, 'b7'), (1, 'R'), (0, '3'), 0], 'root_string': 0, 'name': 'E Shape', 'level': 'basic'},
    'maj7_E': {'frets': [0, 'x', (1, 'b7'), (1, 'R'), (1, '3'), 0], 'root_string': 0, 'name': 'E Shape', 'level': 'basic'},
    'min7_E': {'frets': [0, 'x', (2, '5'), (0, 'b7'), (0, 'b3'), 0], 'root_string': 0, 'name': 'E Shape', 'level': 'basic'},

    # ─── A-string root shapes ───
    'maj_A': {'frets': ['x', 0, (2, '5'), (2, 'R'), (2, '3'), 0], 'root_string': 1, 'name': 'A Shape', 'level': 'basic'},
    'min_A': {'frets': ['x', 0, (2, '5'), (2, 'R'), (1, 'b3'), 0], 'root_string': 1, 'name': 'A Shape', 'level': 'basic'},
    'dom7_A': {'frets': ['x', 0, (2, '5'), 0, (2, '3'), 0], 'root_string': 1, 'name': 'A Shape', 'level': 'basic'},
    'maj7_A': {'frets': ['x', 0, (2, '5'), (1, '7'), (2, '3'), 0], 'root_string': 1, 'name': 'A Shape', 'level': 'basic'},
    'min7_A': {'frets': ['x', 0, (2, '5'), 0, (1, 'b3'), 0], 'root_string': 1, 'name': 'A Shape', 'level': 'basic'},

    # ─── Drop 2 shapes (D-G-B-E strings) ───
    'maj7_drop2': {'frets': ['x', 'x', 0, (2, '5'), (1, '7'), (2, '3')], 'root_string': 2, 'name': 'Drop 2', 'level': 'intermediate'},
    'min7_drop2': {'frets': ['x', 'x', 0, (2, '5'), (1, 'b7'), (1, 'b3')], 'root_string': 2, 'name': 'Drop 2', 'level': 'intermediate'},
    'dom7_drop2': {'frets': ['x', 'x', 0, (2, '5'), (1, 'b7'), (2, '3')], 'root_string': 2, 'name': 'Drop 2', 'level': 'intermediate'},

    # ─── Shell voicings (3-note, strings 5-4-3 or 6-5-4) ───
    'dom7_shell6': {'frets': [0, 'x', (1, 'b7'), (2, '3'), 'x', 'x'], 'root_string': 0, 'name': 'Shell (6th str)', 'level': 'intermediate'},
    'dom7_shell5': {'frets': ['x', 0, (1, 'b7'), (2, '3'), 'x', 'x'], 'root_string': 1, 'name': 'Shell (5th str)', 'level': 'intermediate'},
    'maj7_shell6': {'frets': [0, 'x', (1, '7'), (2, '3'), 'x', 'x'], 'root_string': 0, 'name': 'Shell (6th str)', 'level': 'intermediate'},
    'min7_shell5': {'frets': ['x', 0, (2, 'b7'), (1, 'b3'), 'x', 'x'], 'root_string': 1, 'name': 'Shell (5th str)', 'level': 'intermediate'},
}


def transpose_guitar_voicing(shape_data, root):
    """Transpose a guitar voicing shape to a given root."""
    root_semi = NOTE_TO_SEMI[root]
    root_string = shape_data['root_string']
    open_string_semi = GUITAR_TUNING[root_string]

    # How many frets to shift
    offset = (root_semi - open_string_semi) % 12

    transposed = []
    for f in shape_data['frets']:
        if f == 'x':
            transposed.append('x')
        elif isinstance(f, tuple):
            transposed.append((f[0] + offset, f[1]))
        elif f == 0:
            if offset == 0:
                transposed.append(0)
            else:
                transposed.append(offset)
        else:
            transposed.append(f + offset)

    return transposed


def get_guitar_voicings(root, quality, levels=None):
    """Get guitar voicings for a chord."""
    if levels is None:
        levels = ['basic', 'intermediate', 'advanced']

    voicings = []
    # Find matching shapes
    for key, shape in GUITAR_VOICINGS.items():
        shape_quality = key.rsplit('_', 1)[0]
        if shape_quality == quality and shape['level'] in levels:
            frets = transpose_guitar_voicing(shape, root)
            voicings.append({
                'name': shape['name'],
                'level': shape['level'],
                'frets': frets,
                'chord_symbol': root + CHORD_QUALITIES[quality]['symbol'],
                'root': root,
                'quality': quality,
                'description': f"{shape['name']} voicing",
            })

    return voicings


# ─── Progressions ───────────────────────────────────────────────

PROGRESSIONS = {
    'ii-V-I': {
        'name': 'ii – V – I',
        'description': 'The most fundamental jazz progression',
        'major': [
            {'degree': 'ii', 'quality': 'min7', 'interval': 2},
            {'degree': 'V', 'quality': 'dom7', 'interval': 7},
            {'degree': 'I', 'quality': 'maj7', 'interval': 0},
        ],
    },
    'I-vi-ii-V': {
        'name': 'I – vi – ii – V',
        'description': 'Turnaround progression — the backbone of standards',
        'major': [
            {'degree': 'I', 'quality': 'maj7', 'interval': 0},
            {'degree': 'vi', 'quality': 'min7', 'interval': 9},
            {'degree': 'ii', 'quality': 'min7', 'interval': 2},
            {'degree': 'V', 'quality': 'dom7', 'interval': 7},
        ],
    },
    'iii-VI-ii-V': {
        'name': 'iii – VI – ii – V',
        'description': 'Extended turnaround with secondary dominant feel',
        'major': [
            {'degree': 'iii', 'quality': 'min7', 'interval': 4},
            {'degree': 'VI', 'quality': 'dom7', 'interval': 9},
            {'degree': 'ii', 'quality': 'min7', 'interval': 2},
            {'degree': 'V', 'quality': 'dom7', 'interval': 7},
        ],
    },
    'blues-basic': {
        'name': 'Blues (I – IV – V)',
        'description': 'Basic blues changes',
        'major': [
            {'degree': 'I', 'quality': 'dom7', 'interval': 0},
            {'degree': 'IV', 'quality': 'dom7', 'interval': 5},
            {'degree': 'V', 'quality': 'dom7', 'interval': 7},
        ],
    },
    'minor-ii-V-i': {
        'name': 'ii° – V – i (minor)',
        'description': 'Minor key ii-V-i resolution',
        'major': [
            {'degree': 'iiø', 'quality': 'min7b5', 'interval': 2},
            {'degree': 'V', 'quality': 'dom7b9', 'interval': 7},
            {'degree': 'i', 'quality': 'min7', 'interval': 0},
        ],
    },
    'rhythm-changes-A': {
        'name': 'Rhythm Changes (A section)',
        'description': 'Based on "I Got Rhythm" — the standard of standards',
        'major': [
            {'degree': 'I', 'quality': 'maj7', 'interval': 0},
            {'degree': 'vi', 'quality': 'min7', 'interval': 9},
            {'degree': 'ii', 'quality': 'min7', 'interval': 2},
            {'degree': 'V', 'quality': 'dom7', 'interval': 7},
        ],
    },
}


def realize_progression(prog_key, root_key, octave=3):
    """Turn a progression template into concrete chords in a key."""
    prog = PROGRESSIONS[prog_key]
    chords = []
    root_semi = NOTE_TO_SEMI[root_key]
    for chord_info in prog['major']:
        chord_semi = (root_semi + chord_info['interval']) % 12
        chord_root = NOTES[chord_semi]
        chords.append({
            'root': chord_root,
            'quality': chord_info['quality'],
            'degree': chord_info['degree'],
            'symbol': chord_root + CHORD_QUALITIES[chord_info['quality']]['symbol'],
        })
    return {
        'name': prog['name'],
        'description': prog['description'],
        'key': root_key,
        'chords': chords,
    }


# ─── Curriculum ──────────────────────────────────────────────────

CURRICULUM = [
    # Week 1-2: Basic voicings, ii-V-I and turnarounds in easy keys
    {'weeks': (1, 2), 'levels': ['basic'], 'progressions': ['ii-V-I', 'I-vi-ii-V', 'blues-basic'],
     'keys': ['C', 'F', 'G', 'Bb', 'Eb', 'D'], 'description': 'Basic Voicings'},

    # Week 3-4: Shell voicings
    {'weeks': (3, 4), 'levels': ['basic', 'intermediate'], 'progressions': ['ii-V-I', 'I-vi-ii-V', 'blues-basic'],
     'keys': ['C', 'F', 'Bb', 'Eb', 'Ab', 'G', 'D'], 'description': 'Shell Voicings'},

    # Week 5-6: Drop 2 voicings, turnarounds
    {'weeks': (5, 6), 'levels': ['intermediate'], 'progressions': ['ii-V-I', 'I-vi-ii-V'],
     'keys': KEYS_MAJOR[:8], 'description': 'Drop 2 Voicings'},

    # Week 7-8: Rootless voicings
    {'weeks': (7, 8), 'levels': ['intermediate', 'advanced'], 'progressions': ['ii-V-I', 'I-vi-ii-V', 'iii-VI-ii-V'],
     'keys': KEYS_MAJOR[:10], 'description': 'Rootless Voicings'},

    # Week 9-10: Minor keys
    {'weeks': (9, 10), 'levels': ['intermediate', 'advanced'], 'progressions': ['minor-ii-V-i', 'ii-V-I'],
     'keys': KEYS_MAJOR, 'description': 'Minor Key Voicings'},

    # Week 11-12: Upper structures, all keys
    {'weeks': (11, 12), 'levels': ['advanced'], 'progressions': ['ii-V-I', 'rhythm-changes-A', 'iii-VI-ii-V'],
     'keys': KEYS_MAJOR, 'description': 'Upper Structures & Reharmonization'},

    # Week 13+: Cycle through everything
    {'weeks': (13, 99), 'levels': ['basic', 'intermediate', 'advanced'],
     'progressions': list(PROGRESSIONS.keys()),
     'keys': KEYS_MAJOR, 'description': 'Full Review'},
]

START_DATE = date(2026, 4, 2)


def get_day_number(target_date=None):
    """Get the day number from start date."""
    if target_date is None:
        target_date = date.today()
    return (target_date - START_DATE).days + 1


def get_week_number(day_num):
    """Get week number (1-indexed) from day number."""
    return ((day_num - 1) // 7) + 1


def get_curriculum_for_day(day_num):
    """Get the curriculum stage for a given day."""
    week = get_week_number(day_num)
    for stage in CURRICULUM:
        if stage['weeks'][0] <= week <= stage['weeks'][1]:
            return stage
    return CURRICULUM[-1]


def generate_day(target_date=None, ratings=None):
    """Generate a complete day's content."""
    if target_date is None:
        target_date = date.today()

    day_num = get_day_number(target_date)
    week_num = get_week_number(day_num)
    stage = get_curriculum_for_day(day_num)

    # Deterministic but varied selection based on date
    seed = int(hashlib.md5(str(target_date).encode()).hexdigest(), 16)
    rng = random.Random(seed)

    # Pick key and progression
    key = rng.choice(stage['keys'])
    prog_key = rng.choice(stage['progressions'])

    # Realize the progression
    progression = realize_progression(prog_key, key)

    # Generate voicings for each chord
    piano_chords = []
    guitar_chords = []

    for chord in progression['chords']:
        # Piano voicings at current curriculum levels
        p_voicings = get_voicings_for_chord(
            chord['root'], chord['quality'],
            levels=stage['levels'], octave=3
        )
        piano_chords.append({
            'chord': chord,
            'voicings': p_voicings,
        })

        # Guitar voicings
        g_voicings = get_guitar_voicings(
            chord['root'], chord['quality'],
            levels=stage['levels']
        )
        guitar_chords.append({
            'chord': chord,
            'voicings': g_voicings,
        })

    return {
        'date': str(target_date),
        'day_number': day_num,
        'week_number': week_num,
        'stage_description': stage['description'],
        'levels': stage['levels'],
        'key': key,
        'progression': progression,
        'piano_chords': piano_chords,
        'guitar_chords': guitar_chords,
    }


if __name__ == '__main__':
    # Test
    day = generate_day(date(2026, 4, 2))
    print(f"Day {day['day_number']} | Week {day['week_number']}")
    print(f"Stage: {day['stage_description']}")
    print(f"Key: {day['key']} | Progression: {day['progression']['name']}")
    print()
    for pc in day['piano_chords']:
        print(f"  {pc['chord']['symbol']} ({pc['chord']['degree']})")
        for v in pc['voicings']:
            print(f"    {v['name']}: {', '.join(v['piano_notes'])}")
    print()
    for gc in day['guitar_chords']:
        print(f"  {gc['chord']['symbol']} ({gc['chord']['degree']})")
        for v in gc['voicings']:
            print(f"    {v['name']}: {v['frets']}")
