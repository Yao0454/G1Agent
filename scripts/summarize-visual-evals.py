"""Compare saved visual trials, including missed gestures and false triggers."""
import argparse
import json
from pathlib import Path


def summarize(root):
    cases = json.loads((root / 'cases.json').read_text())
    rows = [json.loads((root / c['id'] / 'result.json').read_text()) for c in cases]
    positive = [r for r in rows if r['case']['expected_skills']]
    negative = [r for r in rows if not r['case']['expected_skills']]
    triggered = lambda r: r.get('decision', {}).get('action') in (
        'execute_skill', 'execute_and_speak', 'speak', 'interrupt'
    )
    return {
        'directory': str(root),
        'total': len(rows),
        'strict_correct': sum(r['correct'] for r in rows),
        'errors': sum('error' in r for r in rows),
        'positive_total': len(positive),
        'correct_gesture': sum(r['correct'] for r in positive),
        'negative_total': len(negative),
        'false_triggers': sum(triggered(r) for r in negative),
        # continue and ignore both cause no action in these independent idle trials.
        # Keep strict scoring above so this does not inflate the original score.
        'idle_continue': sum(r.get('decision', {}).get('action') == 'continue' for r in negative),
        'classes': {
            category: {'total': sum(c['category'] == category for c in cases),
                       'correct': sum(r['correct'] for r in rows if r['case']['category'] == category)}
            for category in sorted({c['category'] for c in cases})
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps([summarize(root) for root in args.directories], indent=2))
