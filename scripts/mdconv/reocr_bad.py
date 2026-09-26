"""글꼴 대응표가 깨져 이상한 글자가 많이 나온 쪽을 찾아 OCR 결과로 바꾼다.

convert.py가 만든 캐시(cache/<sha12>/pNNNN.md)를 검사한다. 한 번 바꾼 쪽은 .md.orig로 원래 결과를 남긴다.
사용법: (mdconv 폴더에서) python3 reocr_bad.py [시간예산초]
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert  # noqa: E402

OK = re.compile(r'[\x00-\x7f -ÿ가-힣ᄀ-ᇿ㄰-㆏一-鿿豈-﫿'
                r' -⯿　-〿㈀-㋿＀-￯①-⓿■-◿-\s]')
BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 140
T0 = time.time()
inv = json.load(open(os.path.expanduser('~/inventory.json')))
sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skip_shas.txt')
skip = set(open(sp).read().split()) if os.path.exists(sp) else set()
inv = [x for x in inv if x['sha256'] not in skip]
n = 0
for x in inv:
    if x['ext'] != 'pdf':
        continue
    d = convert.CACHE + x['sha256'][:12] + '/'
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not re.match(r'p\d{4}\.md$', f):
            continue
        t = open(d + f, encoding='utf-8').read()
        weird = sum(1 for ch in t if not OK.match(ch))
        hang = len(re.findall(r'[가-힣]', t))
        if not ((weird >= 30 and weird > hang * 0.3) or t.count('�') >= 10):
            continue
        if time.time() - T0 > BUDGET:
            print('시간 예산 초과'); sys.exit(3)
        import pymupdf
        page = pymupdf.open(convert.BASE + x['saved_path'])[int(f[1:5]) - 1]
        txt = convert.ocr_page(page)
        os.replace(d + f, d + f + '.orig')
        open(d + f.replace('.md', '.ocr.md'), 'w', encoding='utf-8').write(txt)
        n += 1
print('OCR로 바꾼 쪽', n)
