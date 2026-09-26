"""받아 둔 문서의 새 판이 게시되었는지 확인하고, 있으면 내려받을 작업 목록을 만든다.

각 문서의 제목에서 연도·판 표기를 지운 뒤 발행처 누리집에서 검색하고, 같은 문서이면서 연도가 더 늦은 게시물만 후보로 삼는다.
- 전라남도교육청(jge.go.kr)·경기도교육청(goe.go.kr): 누리집 통합검색(첨부파일·게시판)
- 교육부(moe.go.kr): 정책 게시판 목록의 최근 쪽

사용법:
  python3 editions.py scan  변환기록.json 후보.json [시간예산초]
  python3 editions.py jobs  후보.json 작업폴더      # 수집기 작업(jge·moe)과 경기도교육청 선택 목록을 만든다
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

UA = 'education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'
VERSION_WORDS = r'최종|수정|개정|개정판|안내용|홈페이지|배포용|게시용|탑재용|공개용|원본|표준용량|저해상도|시행|변경안|한글|PDF|내지|본책'
MOE_BOARDS = [(316, '0302'), (72782, '030215'), (327, '0305'), (10165, '0307'), (351, '0310')]


def series_key(title):
    t = re.sub(r'\.(pdf|hwpx?|xlsm)$', '', title, flags=re.I)
    t = re.sub(r'^\s*(\[[^\]]*붙임[^\]]*\]|\(붙임\s*\d*\)|붙임\s*\d*[_.]?|\d+[.\-]\s*|\[PDF\]|\[내지\]|★)\s*', '', t)
    t = re.sub(r'\((?:[^()]*(?:' + VERSION_WORDS + r')[^()]*|\d{4}\.\s*\d+\.\s*\d*\.?[^()]*|v?\d+(\.\d+)*|ver_?\d+)\)', '', t, flags=re.I)
    t = re.sub(r'20\d\d\s*(학년도|년도|년)?', '', t)
    t = re.sub(r'제\s*\d+\s*차', '', t)
    t = re.sub(r'^\s*(최종|수정)\s*[-_]\s*', '', t)
    t = re.sub(r'[_\s]*(탑재용|표준용량|게시용|배포용|최종|수정본|개정판|홈페이지|홈페이지공개용)\s*$', '', t)
    return re.sub(r'[\s·ㆍ.,_\-()\[\]「」『』\'"?]', '', t)


def year_of(title):
    ys = [int(y) for y in re.findall(r'(20\d\d)', title)]
    return max(ys) if ys else 0


def query_of(title):
    t = re.sub(r'\.(pdf|hwpx?)$', '', title, flags=re.I)
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]|20\d\d\s*(학년도|년도|년)?|[★☆]', ' ', t)
    t = re.sub(r'[·ㆍ_\-.,]', ' ', t)
    words = [w for w in t.split() if len(w) > 1 and not re.fullmatch(r'\d+', w)]
    return ' '.join(words[:6])


def curl(args):
    return subprocess.run(['curl', '-sS', '-m', '40', '-A', UA] + args, capture_output=True).stdout.decode('utf-8', 'replace')


def jge_search(q, menu):
    data = urllib.parse.urlencode({'qt': q, 'menu': menu, 'section': menu, 'field': '@title', 'rf': '@date', 'nh': 20,
                                   'st': 1, 'searchType': '2', 'adv': '0', 'sw': '0'})
    t = curl(['-X', 'POST', '-H', 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8', '--data', data,
              'https://www.jge.go.kr/search/front/Search.jsp'])
    out = []
    for m in re.finditer(r'<dl class="C_Cts">(.*?)</dl>', t, re.S):
        a = re.search(r'<a href="([^"]+)" title="([^"]*)"', m.group(1))
        if a:
            d = re.search(r'\[(\d{4}\.\d{2}\.\d{2})\]', m.group(1))
            out.append(dict(title=html.unescape(a.group(2)), url=html.unescape(a.group(1)), date=d.group(1) if d else ''))
    return out


def goe_search(q, menu):
    data = urllib.parse.urlencode({'qt': q, 'menu': menu, 'section': '', 'field': '', 'rf': '@date', 'nh': 20, 'st': 1,
                                   'searchType': '2', 'adv': '0', 'sw': '0'})
    t = curl(['-X', 'POST', '-H', 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8', '--data', data,
              'https://www.goe.go.kr/search/front/Search.jsp'])
    out = []
    for li in re.findall(r'<li class="li">(.*?)</li>\s*(?=<li class="li">|</ul>)', t, re.S):
        a = re.search(r'<a href="([^"]+)"[^>]*title="([^"]*)"', li)
        if a:
            d = re.search(r'i-date">([^<]*)<', li)
            out.append(dict(title=html.unescape(a.group(2)), url=html.unescape(a.group(1)), date=d.group(1) if d else ''))
    return out


def moe_recent(pages=3):
    out = []
    for bid, m in MOE_BOARDS:
        for p in range(1, pages + 1):
            t = curl([f'https://www.moe.go.kr/boardCnts/listRenew.do?boardID={bid}&m={m}&s=moe&page={p}'])
            for r in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S):
                g = re.search(r"goView\('(\d+)',\s*'(\d+)'[^)]*\)[^>]*title=\"([^\"]*)\"", r)
                if g:
                    d = re.search(r'(\d{4}-\d{2}-\d{2})', r)
                    out.append(dict(title=html.unescape(g.group(3)).strip(), date=d.group(1) if d else '',
                                    url=f'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID={bid}&boardSeq={g.group(2)}&lev=0&m={m}&s=moe&opType=N'))
            time.sleep(0.3)
    return out


def scan(record_path, out_path, budget=140):
    rows = [r for r in json.load(open(record_path)) if r.get('status') == '완료']
    prev = json.load(open(out_path)) if os.path.exists(out_path) else {'checked': [], 'candidates': []}
    t0 = time.time()
    moe = None
    for r in rows:
        key = r['group'] + '|' + r['fid']
        if key in prev['checked']:
            continue
        if time.time() - t0 > budget:
            json.dump(prev, open(out_path, 'w'), ensure_ascii=False, indent=1)
            print('시간 예산 초과, 다음 실행에서 이어서 합니다')
            return False
        k, y = series_key(r['title']), year_of(r['title'])
        if not y:  # 연도가 없는 문서는 판을 가를 수 없어 건너뛴다
            prev['checked'].append(key)
            continue
        if r['group'] == '교육부':
            if moe is None:
                moe = moe_recent()
            results = moe
        else:
            fn = goe_search if r['group'] == '경기도교육청' else jge_search
            q = query_of(r['title'])
            results = fn(q, '첨부파일') + fn(q, '기타게시판' if r['group'] == '경기도교육청' else '게시판')
            time.sleep(0.3)
        for x in results:
            if series_key(x['title']) == k and year_of(x['title']) > y and x['url'] != r.get('post'):
                cand = dict(group=r['group'], old_fid=r['fid'], old_title=r['title'], new_title=x['title'], url=x['url'], date=x['date'])
                if cand['url'] not in [c['url'] for c in prev['candidates']]:
                    prev['candidates'].append(cand)
                    print('새 판 후보', r['fid'], r['title'], '→', x['title'], x['url'])
        prev['checked'].append(key)
    json.dump(prev, open(out_path, 'w'), ensure_ascii=False, indent=1)
    print('확인', len(prev['checked']), '후보', len(prev['candidates']))
    return True


def jobs(cand_path, workdir):
    c = json.load(open(cand_path))['candidates']
    os.makedirs(workdir, exist_ok=True)
    stamp = time.strftime('%Y%m%d')
    region = {'전라남도교육청': '전남_새판', '교육부': '교육부_지침', '경기도교육청': '경기도교육청'}
    collector = [dict(id=f'U{stamp}-{i}', kind='page', title='새 판 ' + x['new_title'], region=region[x['group']], url=x['url'],
                      max_attachments=12, include_hwp=True) for i, x in enumerate(c, 1) if x['group'] != '경기도교육청']
    goe = [dict(pattern=x['new_title'], mode='post', title=x['new_title'], url=x['url'], date=x['date']) for x in c if x['group'] == '경기도교육청']
    json.dump(collector, open(os.path.join(workdir, 'collector_jobs.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(goe, open(os.path.join(workdir, 'goe_selected.json'), 'w'), ensure_ascii=False, indent=1)
    print('수집기 작업', len(collector), '경기도교육청', len(goe))


if __name__ == '__main__':
    if sys.argv[1] == 'scan':
        ok = scan(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 140)
        sys.exit(0 if ok else 3)
    elif sys.argv[1] == 'jobs':
        jobs(sys.argv[2], sys.argv[3])
