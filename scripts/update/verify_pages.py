"""목록(inventory.json)의 PDF 쪽수를 verify.json에 채운다. 이미 있는 항목은 건너뛴다."""
import json
import os

import pymupdf

H = os.path.expanduser('~')
inv = json.load(open(H + '/inventory.json'))
p = H + '/verify.json'
v = json.load(open(p)) if os.path.exists(p) else {}
n = 0
for x in inv:
    if x['ext'] == 'pdf' and not (v.get(x['sha256']) or {}).get('pages'):
        try:
            v.setdefault(x['sha256'], {})['pages'] = pymupdf.open(H + '/epc_out/' + x['saved_path']).page_count
            n += 1
        except Exception as e:
            v.setdefault(x['sha256'], {})['error'] = repr(e)
json.dump(v, open(p, 'w'), ensure_ascii=False)
print('쪽수 채움', n)
