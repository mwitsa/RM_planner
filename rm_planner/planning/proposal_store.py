"""Preferences and explicit approval snapshots; no inventory mutations."""
import json
from pathlib import Path


def load_preferences(path):
    path = Path(path)
    if not path.exists():
        return {'settings': {}, 'profiles': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ('settings', 'profiles')):
        raise ValueError('ไฟล์ตั้งค่า Plan ไม่ถูกต้อง')
    return data


def save_preferences(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def save_approval(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
