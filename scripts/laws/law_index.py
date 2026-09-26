"""법령 폴더의 목록(00_법령목록.md)을 만든다. 초·중등교육법·시행령·시행규칙의 어느 조문이 어떤 법령을 인용하는지도 함께 적는다.

사용법: python3 law_index.py 법령폴더
"""
import json
import os
import re
import sys
import urllib.parse

ROOT = sys.argv[1]
state = json.load(open(os.path.join(ROOT, '_법령상태.json'), encoding='utf-8'))


def norm(s):
    return re.sub(r'[\s·ㆍ]', '', s)


files = {}
for dp, _, fs in os.walk(ROOT):
    if '_구판' in dp:
        continue
    for f in fs:
        if f.endswith('.md') and not f.startswith('00_'):
            files[norm(f[:-3])] = os.path.relpath(os.path.join(dp, f), ROOT)


def meta(path):
    t = open(os.path.join(ROOT, path), encoding='utf-8').read(3000)
    g = lambda k: (re.search(rf'^{k}: "(.*)"$', t, re.M) or [None, ''])[1]
    return g('law_kind'), g('effective'), g('promulgated') or g('issued')


# 초·중등교육법 계열의 조문별 인용 관계
cites = {}
for base in ('초ㆍ중등교육법', '초ㆍ중등교육법 시행령', '초ㆍ중등교육법 시행규칙'):
    p = files.get(norm(base))
    if not p:
        continue
    text = open(os.path.join(ROOT, p), encoding='utf-8').read()
    for sec in re.split(r'\n(?=#### )', text):
        m = re.match(r'#### (제\d+조(?:의\d+)?)\(([^)]*)\)', sec)
        if not m:
            continue
        for name in set(re.findall(r'「([^」]{2,40}?)」', sec)):
            k = norm(name)
            if k in files and k != norm(base):
                short = base.replace('초ㆍ중등교육법', '법').replace('법 시행령', '영').replace('법 시행규칙', '규칙')
                cites.setdefault(k, []).append(f'{short} {m.group(1)}({m.group(2)})')

groups = {}
for k, p in sorted(files.items(), key=lambda kv: kv[1]):
    groups.setdefault(os.path.dirname(p), []).append((k, p))

L = ['# 학교 업무 관련 법령 목록', '',
     '법제처 국가법령정보센터의 현행 법령을 조문 단위 Markdown으로 정리했습니다. 법령 본문은 저작권법 제7조에 따라 보호받지 않는 저작물이므로 자유롭게 쓸 수 있습니다. 다만 효력이 있는 원문은 국가법령정보센터에서 확인하십시오.', '',
     '- 각 파일 머리에 공포일, 시행일, 원문 주소가 있습니다. 부칙은 최근 3개만 실었습니다.',
     '- 「초·중등교육법 인용」 열에는 초·중등교육법(법)·시행령(영)·시행규칙(규칙)의 어느 조문이 그 법령을 인용하는지 적었습니다.',
     '- 법령이 개정되면 정기 점검에서 새 판으로 바꾸고, 구판은 `_구판` 폴더에 시행일을 붙여 남깁니다.', '']
for g, items in groups.items():
    L += [f'## {g}', '', '| 법령 | 종류 | 시행일 | 초·중등교육법 인용 |', '|---|---|---|---|']
    for k, p in items:
        kind, eff, _ = meta(p)
        c = cites.get(k, [])
        cs = ', '.join(c[:6]) + (f' 외 {len(c) - 6}곳' if len(c) > 6 else '')
        L.append(f"| [{os.path.basename(p)[:-3]}](<{p}>) | {kind} | {eff} | {cs} |")
    L.append('')
open(os.path.join(ROOT, '00_법령목록.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('목록', len(files))
