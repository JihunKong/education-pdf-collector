"""법령 목록을 현행 기준으로 받아 Markdown으로 저장하고, 새 판이 나오면 구판을 _구판 폴더로 옮긴다.

사용법: python3 fetch_laws.py law_list.json 출력폴더 [상태파일]
상태파일에는 법령마다 법령일련번호(MST)·시행일자를 기록한다. 다시 실행하면 번호가 바뀐 법령만 새로 받는다.
"""
import json
import os
import re
import shutil
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawlib  # noqa: E402

LIST, OUT = sys.argv[1], sys.argv[2]
STATE = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, '_법령상태.json')
cfg = json.load(open(LIST, encoding='utf-8'))
state = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
os.makedirs(OUT, exist_ok=True)


def norm(s):
    return re.sub(r'[\s·ㆍ]', '', s)


def fname(name):
    return re.sub(r'[\\/:*?"<>|]', ' ', name).strip() + '.md'


BUDGET = float(os.environ.get('LAW_BUDGET', '0'))
T0 = time.time()
changes = []
missing = []
for grp in cfg['groups']:
    folder = os.path.join(OUT, grp['folder'])
    os.makedirs(folder, exist_ok=True)
    for target, names in (('law', grp.get('law', [])), ('admrul', grp.get('admrul', []))):
        for name in names:
            try:
                hits = lawlib.search(target, name)
            except Exception as e:
                missing.append((name, f'검색 실패 {e!r}'))
                continue
            key_name = '법령명한글' if target == 'law' else '행정규칙명'
            key_id = '법령일련번호' if target == 'law' else '행정규칙일련번호'
            cand = [h for h in hits if norm(h.get(key_name, '')) == norm(name)
                    and h.get('현행연혁코드', '현행') in ('현행', '')]
            if not cand:
                missing.append((name, '정확히 일치하는 현행 법령 없음: ' + ', '.join(h.get(key_name, '') for h in hits[:5])))
                continue
            if BUDGET and time.time() - T0 > BUDGET:
                print('시간 예산 초과, 다음 실행에서 이어서 합니다')
                json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                sys.exit(3)
            h = cand[0]
            key = h[key_id]
            path = os.path.join(folder, fname(h[key_name]))
            old = state.get(name)
            if old and old.get('key') == key and os.path.exists(path):
                continue
            xml = lawlib.fetch(target, key)
            if target == 'law':
                src = 'https://www.law.go.kr/법령/' + urllib.parse.quote(h[key_name].replace(' ', ''))
                meta, md = lawlib.render_law(xml, src)
            else:
                src = 'https://www.law.go.kr/행정규칙/' + urllib.parse.quote(h[key_name].replace(' ', ''))
                meta, md = lawlib.render_admrul(xml, src)
            if old and os.path.exists(path):
                # 구판 보존: 시행일을 붙여 _구판 폴더로 옮긴다
                arch = os.path.join(OUT, '_구판')
                os.makedirs(arch, exist_ok=True)
                shutil.move(path, os.path.join(arch, fname(h[key_name])[:-3] + f'_시행{old.get("effective", "")}.md'))
                changes.append((name, old.get('effective'), meta.get('effective')))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(md)
            state[name] = dict(key=key, target=target, effective=meta.get('effective'), file=os.path.relpath(path, OUT),
                               promulgated=meta.get('promulgated') or meta.get('issued'), checked=time.strftime('%Y-%m-%d'))
            json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            time.sleep(0.3)
for name, v in state.items():
    v['checked'] = time.strftime('%Y-%m-%d')
json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('법령', len(state), '개정 반영', len(changes), '못 찾음', len(missing))
for c in changes:
    print('개정', c)
for m in missing:
    print('못 찾음', m)
