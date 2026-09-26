"""수집 원문 전체를 발행처별 폴더(전라남도교육청·교육부·경기도교육청)와 법령 폴더로 묶어 Markdown 트리를 만든다.

같은 문서의 판이 여러 개면 가장 새 판만 본 폴더에 두고, 나머지는 `_구판` 폴더로 옮긴 뒤 머리 정보에 대체한 판을 적는다.
다시 실행하면 새로 받은 판이 자동으로 앞 판을 대체한다.

사용법: python3 build_md.py 출력폴더 전남수집파일목록.csv 요청대조표.csv [법령폴더]
"""
import collections
import csv
import json
import os
import re
import shutil
import sys

HOME = os.path.expanduser('~')
CACHE = HOME + '/mdconv/cache/'
OUT, FILELIST, REQ = sys.argv[1], sys.argv[2], sys.argv[3]
LAWS = sys.argv[4] if len(sys.argv) > 4 else ''
inv = {x['sha256']: x for x in json.load(open(HOME + '/inventory.json'))}
ver = json.load(open(HOME + '/verify.json'))
state = json.load(open(HOME + '/epc_out/state.json'))['records']
man_p = HOME + '/mdconv/new_manifest.json'
manifest = json.load(open(man_p)) if os.path.exists(man_p) else {'convert': [], 'skip_alt': []}
files = list(csv.DictReader(open(FILELIST, encoding='utf-8-sig')))
req = {r['id']: r for r in csv.DictReader(open(REQ, encoding='utf-8-sig'))}

STATUS_SHORT = {
    '해결: 공식 PDF 서지 일치': '대조 완료(공식 PDF 일치)',
    '이전 완료 판정 유지': '대조 완료(공식 PDF 일치)',
    '원본 확보: 공식 게시물에 HWP·HWPX만 있음': '원본 확보(HWP·HWPX 원본)',
    '후보: 명칭·판 표기 차이, 확인 필요': '후보(명칭·판 표기 차이)',
    '관련 자료만': '관련 자료(요청 문서와 판이나 범위가 다름)',
}
TITLE = {
    'N20260926-003': ('학교생활기록 작성 및 관리지침(교육부훈령 제504호, 전북특별자치도교육청 재게시본)', '학교생활기록 작성 및 관리지침(교육부훈령 제504호).pdf'),
    'N20260926-004': ('2025학년도 고교학점제 운영 지원 계획', '2025학년도 고교학점제 운영 지원 계획.pdf'),
    'N20260926-007': ('2026. 유아 2030교실 길라잡이(v2.0)', '2026. 유아 2030교실 길라잡이(v2.0).pdf'),
    'N20260926-010': ('2025년 개정 직업계고 현장실습 운영 매뉴얼', '2025년 개정 직업계고 현장실습 운영 매뉴얼.pdf'),
    'N20260926-011': ('(전남) 고교학점제 운영 안내서', '(전남)고교학점제+운영+안내서.pdf'),
    'N20260926-015': ('2025. 교육공무원 인사실무(최종)', '2025. 교육공무원 인사실무(최종).pdf'),
    'N20260926-016': ('2026. 교육공무원 인사실무(홈페이지 탑재용)', '2026. 교육공무원 인사실무(홈페이지 탑재용).pdf'),
    'N20260926-113': ('2025. 전남 고교학점제 미리보기(워크북) 교사용(학교 누리집 재게시본)', '학교 누리집 재게시 첨부 PDF(nagan.ms.jne.kr)'),
    'N20260926-114': ('2025. 전남 고교학점제 미리보기(워크북) 학생용(학교 누리집 재게시본)', '학교 누리집 재게시 첨부 PDF(juam.ms.jne.kr)'),
}
# 교육부가 전국에 배포하는 문서: 어느 교육청 누리집에서 받았든 교육부 판으로 묶어 판을 비교한다
NATIONAL = r'학교생활기록부 기재요령|학교폭력 사안처리 가이드북|교원자격검정 실무편람|폭력 예방교육 운영안내|특별교부금 교부'
# 법령 폴더의 판이 이 문서를 대체한다
LAW_SUPERSEDES = {'N20260926-003': '법령/04_교육과정·학업/학교생활기록 작성 및 관리지침.md'}

CATS = [
    ('고교학점제', r'고교학점제|공동교육과정|과목 선택|고시 외 과목|최소 성취'),
    ('교육공무직 및 노무', r'근무시간 면제|단체협약|노동조합|정책협의'),
    ('미래교실 및 기초학력', r'2030교실'),
    ('교육과정 및 학사', r'현장실습'),
    ('장학 및 연수', r'연수 운영계획|법정의무교육|교육연수'),
    ('학업성적 및 생활기록부', r'학교생활기록|기재요령|학업성적|학적|학생평가'),
    ('학교운영위원회', r'학교운영위원회|학부모'),
    ('교육공무직 및 노무', r'교육공무직|급여 업무'),
    ('인사 및 상담', r'인사|계약제|교원자격|교장공모|교원 연수|원어민|Wee|상담|보결'),
    ('학생 생활 및 안전', r'학교폭력|교육활동 보호|생활규정|성희롱|성폭력|폭력 예방|현장체험|재난|감염병|안전|학업중단|학교민원|민원 처리'),
    ('재정 및 복지', r'회계|예산|교육비|교육급여|폐교재산|맞춤형복지'),
    ('미래교실 및 기초학력', r'기초학력|디지털|튜터|특수교육|개별화|늘봄|방과후|돌봄'),
    ('인성 및 특별교육', r'인성|진로|예술교육|독도|다문화|이주배경|외국어|독서|도서관|체육|마약'),
    ('교육과정 및 학사', r'교육과정|자율시간|학급편성|자율과제|통합운영학교'),
    ('일반 행정 및 보안', r'보안|정보공개|정보공시|민원편람|감사|공직복무|주요업무계획|학교평가|장학|입학전형'),
]


def classify(title):
    for c, p in CATS:
        if re.search(p, title):
            return c
    return '기타'


def publisher(sp):
    if '/교육부_전북재게시/' in sp:
        return '교육부(전북특별자치도교육청 재게시)'
    if '/교육부/' in sp or '/교육부_지침/' in sp or 'C-T130-4-1' in sp:
        return '교육부'
    if '/경기도교육청/' in sp:
        return '경기도교육청'
    if 'K-T015-1-1' in sp:
        return '광주광역시교육청'
    if '/전남_연수원/' in sp:
        return '전라남도교육청교육연수원'
    if 'K-T051-' in sp:
        return '교육부·국가기초학력지원센터(전라남도교육청 게시)'
    return '전라남도교육청'


def group_of(pub):
    if pub.startswith('교육부'):
        return '교육부'
    if pub == '경기도교육청':
        return '경기도교육청'
    return '전라남도교육청'


def safe(s, n=70):
    s = re.sub(r'\.(pdf|hwpx?|xlsm)$', '', s, flags=re.I)
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', ' ', s)
    s = re.sub(r'[★☆]', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' ._')
    return s[:n].strip()


def clean_ocr(t):
    out = []
    for l in t.split('\n'):
        s = l.strip()
        if not s:
            if out and out[-1] != '':
                out.append('')
            continue
        if re.search(r'[가-힣]', s) or re.search(r'\d{2,}', s) or re.search(r'[A-Za-z]{3,}', s):
            out.append(s)
    return '\n'.join(out).strip()


def yq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


VERSION_WORDS = r'최종|수정|개정|개정판|안내용|홈페이지|배포용|게시용|탑재용|공개용|원본|표준용량|저해상도|시행|변경안|한글|PDF|내지|본책'


def series_key(title):
    """판을 비교하려고 연도·판 표기를 지운 제목."""
    t = re.sub(r'\.(pdf|hwpx?|xlsm)$', '', title, flags=re.I)
    t = re.sub(r'^\s*(\[[^\]]*붙임[^\]]*\]|\(붙임\s*\d*\)|붙임\s*\d*[_.]?|\d+[.\-]\s*|\[PDF\]|\[내지\]|★)\s*', '', t)
    t = re.sub(r'\((?:[^()]*(?:' + VERSION_WORDS + r')[^()]*|\d{4}\.\s*\d+\.\s*\d*\.?[^()]*|v?\d+(\.\d+)*|ver_?\d+)\)', '', t, flags=re.I)
    t = re.sub(r'20\d\d\s*(학년도|년도|년)?', '', t)
    t = re.sub(r'제\s*\d+\s*차', '', t)
    t = re.sub(r'^\s*(최종|수정)\s*[-_]\s*', '', t)
    t = re.sub(r'[_\s]*(탑재용|표준용량|게시용|배포용|최종|수정본|개정판|홈페이지|홈페이지공개용)\s*$', '', t)
    t = re.sub(r'[\s·ㆍ.,_\-()\[\]「」『』\'"?]', '', t)
    return t


def year_of(title, date=''):
    ys = [int(y) for y in re.findall(r'(20\d\d)', title)]
    return (max(ys) if ys else 0, date)


# ---------- 문서 목록 만들기 ----------
docs = []
for f in files:
    sha = f['sha256']
    x = inv[sha]
    title, orig = TITLE.get(f['file_id'], (safe(f['label'], 120), f['label']))
    ids = re.findall(r'T\d{3}', f['request_ids'])
    pub = publisher(x['saved_path'])
    cat = req[ids[0]]['category'] if ids and ids[0] in req else classify(title)
    docs.append(dict(fid=f['file_id'].replace('N20260926-', 'N'), full_id=f['file_id'], sha=sha, title=title, orig=orig,
                     fmt=f['format'], pages=int(f['pdf_pages'] or 0), post=f['post_url'], url=f['file_url'],
                     pub=pub, cat=cat, ids=ids, date=''))
known = {d['sha'] for d in docs}
new_recs = [v for v in state.values() if v.get('sha256') in manifest['convert'] and v.get('sha256') not in known
            and v.get('status') == 'downloaded' and v.get('saved_path')]
seq = collections.Counter()
for v in sorted(new_recs, key=lambda v: v['id']):
    x = inv.get(v['sha256'])
    if not x:
        continue
    pub = publisher(x['saved_path'])
    pre = {'교육부': 'M', '경기도교육청': 'G'}.get(group_of(pub), 'N')
    seq[pre] += 1
    num = seq[pre] + (len(files) if pre == 'N' else 0)
    title = safe(re.sub(r'^\s*(\[붙임\s*\d*\]|\(붙임\s*\d*\)|붙임\s*\d*[_.]?|\[PDF\]|\[내지\])\s*', '', v['title']), 120)
    docs.append(dict(fid=f'{pre}{num:03d}', full_id=v['id'], sha=v['sha256'], title=title, orig=v['title'],
                     fmt=x['ext'], pages=(ver.get(v['sha256'], {}) or {}).get('pages') or 0, post=v.get('parent_url', ''),
                     url=v.get('url', ''), pub=pub, cat=classify(title), ids=[], date=v.get('checked_at', '')))

# ---------- 판 비교 ----------
for d in docs:
    d['group'] = group_of(d['pub'])
    d['cmp_group'] = '교육부' if re.search(NATIONAL, d['title']) else d['group']
    d['key'] = series_key(d['title'])
series = collections.defaultdict(list)
for d in docs:
    series[(d['cmp_group'], d['key'])].append(d)
for k, ds in series.items():
    if len(ds) < 2:
        continue
    years = {year_of(d['title'])[0] for d in ds}
    if len(years) < 2:
        continue  # 같은 해의 여러 판은 모두 둔다(학교급별·서식편 등)
    latest = max(years)
    keep = [d for d in ds if year_of(d['title'])[0] == latest]
    for d in ds:
        if d not in keep:
            d['superseded_by'] = ', '.join(f"{x['fid']} {x['title']}" for x in keep)
for d in docs:
    if d['full_id'] in LAW_SUPERSEDES and LAWS:
        d['superseded_by'] = LAW_SUPERSEDES[d['full_id']] + ' (국가법령정보센터 현행 훈령)'

# ---------- 파일 쓰기 ----------
rows = []
for d in docs:
    c = CACHE + d['sha'][:12] + '/'
    body, ocr, missing = [], [], []
    if d['fmt'] == 'pdf':
        n = d['pages'] or len([f for f in os.listdir(c) if re.match(r'p\d{4}(\.ocr)?\.md$', f)]) if os.path.isdir(c) else d['pages']
        for i in range(1, (n or 0) + 1):
            p, po = c + f'p{i:04d}.md', c + f'p{i:04d}.ocr.md'
            if os.path.exists(p):
                t, tag = open(p, encoding='utf-8').read().strip(), ''
            elif os.path.exists(po):
                t = clean_ocr(open(po, encoding='utf-8').read()); ocr.append(i)
                tag = ' (텍스트 층이 없어 OCR로 추출함. 오탈자와 순서 오류가 있을 수 있음)'
            else:
                missing.append(i); continue
            body.append(f'<!-- 원문 {i}쪽{tag} -->\n\n{t}' if t else f'<!-- 원문 {i}쪽: 추출된 글자 없음 -->')
        d['pages'] = n or 0
    else:
        p = c + 'whole.md'
        if os.path.exists(p):
            body.append(open(p, encoding='utf-8').read().strip())
        else:
            missing.append('whole')
    if missing or not body:
        rows.append(dict(d, status='미완료', md_path='', md_bytes=0, ocr_pages=len(ocr)))
        continue
    reqs = [f"{i} {req[i]['requested_filename']} [{STATUS_SHORT.get(req[i]['claude_20260926_status'], req[i]['claude_20260926_status'])}]"
            for i in d['ids'] if i in req]
    sup = d.get('superseded_by')
    fm = ['---', f'title: {yq(d["title"])}', f'file_id: {d["fid"]}', f'publisher: {yq(d["pub"])}',
          f'category: {yq(d["cat"])}', f'original_format: {d["fmt"]}', f'original_file: {yq(d["orig"])}',
          f'original_pages: {d["pages"]}' if d['pages'] else 'original_pages: ""',
          f'source_post: {yq(d["post"])}', f'source_file_url: {yq(d["url"])}', f'sha256: {d["sha"]}',
          'requests:' + ('' if reqs else ' []')] + [f'  - {yq(r)}' for r in reqs] + [
          f'ocr_pages: {len(ocr)}'] + ([f'superseded_by: {yq(sup)}'] if sup else []) + [
          'license_note: "공공기관 게시 자료입니다. 다른 사람에게 배포하기 전에 원 게시물의 공공누리 유형과 이용 조건을 확인하십시오."',
          'conversion_note: "원문을 자동 변환한 파일입니다. 표·도식·이미지는 일부 손실될 수 있으므로, 중요한 수치와 규정은 원문과 대조하십시오."',
          '---', '']
    head = [f'# {d["title"]}', '']
    if sup:
        head += [f'> 이 파일은 구판입니다. 새 판: {sup}', '']
    head += [f'- 발행·게시: {d["pub"]}',
             f'- 원문 파일: {d["orig"]} ({d["fmt"].upper()}' + (f', {d["pages"]}쪽' if d['pages'] else '') + ')',
             f'- 출처 게시물: {d["post"] or "게시물 주소 미확인(첨부 직접 주소)"}',
             '- 자동 변환본이므로 표와 그림은 원문과 대조하십시오.' + (f' 이 가운데 {len(ocr)}쪽은 글자 층이 없거나 글꼴 정보가 깨져 OCR(문자 인식)로 추출했습니다.' if ocr else ''), '']
    base = os.path.join(OUT, '_구판', d['group']) if sup else os.path.join(OUT, d['group'])
    folder = os.path.join(base, safe(d['cat'], 40))
    os.makedirs(folder, exist_ok=True)
    stem = safe(d['title'])
    while len(stem.encode('utf-8')) > 150:
        stem = stem[:-1].rstrip()
    path = os.path.join(folder, f'{d["fid"]}_{stem}.md')
    text = '\n'.join(fm) + '\n'.join(head) + '\n' + '\n\n'.join(body).strip() + '\n'
    open(path, 'w', encoding='utf-8').write(text)
    rows.append(dict(d, status='구판' if sup else '완료', md_path=os.path.relpath(path, OUT), md_bytes=len(text.encode()), ocr_pages=len(ocr)))

# ---------- 법령 복사 ----------
law_n = 0
if LAWS and os.path.isdir(LAWS):
    dst = os.path.join(OUT, '법령')
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(LAWS, dst, ignore=shutil.ignore_patterns('_법령상태.json'))
    law_n = sum(1 for dp, _, fs in os.walk(dst) if '_구판' not in dp for f in fs if f.endswith('.md') and not f.startswith('00_'))

json.dump(rows, open(os.path.join(OUT, '_변환기록.json'), 'w'), ensure_ascii=False, indent=1, default=str)

# ---------- 목록 ----------
cur = [r for r in rows if r['status'] == '완료']
old = [r for r in rows if r['status'] == '구판']
L = ['# 교육자료 Markdown 변환본 목록', '',
     f'전라남도교육청·교육부·경기도교육청 누리집에서 받은 원문을 Markdown으로 변환했습니다. 원문 파일 1개가 Markdown 파일 1개입니다. 현행판 {len(cur)}개, 구판 {len(old)}개, 법령 {law_n}개가 있습니다.', '',
     '## 폴더 구성', '',
     '- `전라남도교육청`, `교육부`, `경기도교육청`: 발행처별 자료를 업무 분류 폴더로 나누었습니다. 전라남도교육청 누리집에서 받았더라도 교육부가 발행한 문서는 `교육부` 폴더에 두었습니다.',
     '- `법령`: 초·중등교육법·시행령·시행규칙과 학교 업무에 자주 쓰는 법령·훈령·예규·고시를 조문 단위로 정리했습니다. 자세한 목록은 `법령/00_법령목록.md`에 있습니다.',
     '- `_구판`: 같은 문서의 새 판을 받으면 앞 판을 이 폴더로 옮깁니다. 구판 파일 머리에는 대체한 새 판이 적혀 있습니다. 새 판과 비교할 때만 쓰십시오.', '',
     '## 사용 방법', '',
     '- Claude에서 프로젝트를 만든 뒤, 담당 업무에 필요한 폴더나 파일만 골라 프로젝트 지식에 올리십시오. 모든 파일을 한꺼번에 올리면 프로젝트 용량을 빠르게 채웁니다.',
     '- 각 파일 머리의 YAML 정보에 원문 제목, 출처 게시물 주소, SHA-256이 있습니다. 답변의 근거를 확인할 때 이 주소로 원문을 여십시오.',
     '- 본문에는 `<!-- 원문 12쪽 -->` 같은 쪽 표시가 있습니다. Claude에게 쪽 번호와 함께 인용하도록 요청하면 원문과 대조하기 쉽습니다.',
     '- OCR 쪽이 있는 파일은 원문 PDF에 글자 층이 없거나 글꼴 정보가 깨져 문자 인식으로 추출한 부분입니다. 수치와 규정은 반드시 원문으로 확인하십시오.',
     '- 공공기관 게시 자료라도 공공누리 유형에 따라 출처 표시, 상업적 이용 금지, 변경 금지 조건이 붙습니다. 다른 사람에게 배포하기 전에 원 게시물의 이용 조건을 확인하십시오. 법령 본문은 저작권법 제7조에 따라 자유롭게 쓸 수 있습니다.', '']
for g in ('전라남도교육청', '교육부', '경기도교육청'):
    gs = [r for r in cur if r['group'] == g]
    L += [f'## {g} ({len(gs)}개)', '']
    bycat = collections.defaultdict(list)
    for r in gs:
        bycat[r['cat']].append(r)
    for cat in sorted(bycat):
        L += [f'### {cat}', '', '| 파일 | 형식 | 쪽수 | OCR 쪽 | 관련 요청 | 크기 |', '|---|---|---:|---:|---|---:|']
        for r in sorted(bycat[cat], key=lambda r: r['fid']):
            L.append(f"| [{os.path.basename(r['md_path'])[:-3]}](<{r['md_path']}>) | {r['fmt'].upper()} | {r['pages'] or ''} | {r['ocr_pages'] or ''} | {', '.join(r['ids']) or ''} | {r['md_bytes'] / 1000:.0f}KB |")
        L.append('')
if old:
    L += [f'## 구판 ({len(old)}개)', '', '| 구판 | 새 판 |', '|---|---|']
    for r in sorted(old, key=lambda r: r['fid']):
        L.append(f"| [{os.path.basename(r['md_path'])[:-3]}](<{r['md_path']}>) | {r['superseded_by']} |")
    L.append('')
L += ['## 변환하지 못한 자료', '', '- 이전 작업에서 받은 기존 71개 파일(D·A 계열)은 원본이 이번 작업 환경에 없어 변환하지 않았습니다.', '']
open(os.path.join(OUT, '00_목록.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('현행', len(cur), '구판', len(old), '미완료', len([r for r in rows if r['status'] == '미완료']), '법령', law_n)
