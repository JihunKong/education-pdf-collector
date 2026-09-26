"""캐시된 쪽·파일 단위 Markdown을 합쳐 원문 파일 1개당 .md 1개를 만들고 목록을 쓴다.
사용법: python3 assemble.py 출력폴더 수집파일목록.csv 요청대조표.csv
"""
import csv, json, os, re, sys

HOME = os.path.expanduser('~')
CACHE = HOME + '/mdconv/cache/'
OUT, FILELIST, REQ = sys.argv[1], sys.argv[2], sys.argv[3]
inv = {x['sha256']: x for x in json.load(open(HOME + '/inventory.json'))}
files = list(csv.DictReader(open(FILELIST, encoding='utf-8-sig')))
req = {r['id']: r for r in csv.DictReader(open(REQ, encoding='utf-8-sig'))}

STATUS_SHORT = {
    '해결: 공식 PDF 서지 일치': '대조 완료(공식 PDF 일치)',
    '이전 완료 판정 유지': '대조 완료(공식 PDF 일치)',
    '원본 확보: 공식 게시물에 HWP·HWPX만 있음': '원본 확보(HWP·HWPX 원본)',
    '후보: 명칭·판 표기 차이, 확인 필요': '후보(명칭·판 표기 차이)',
    '관련 자료만': '관련 자료(요청 문서와 판이나 범위가 다름)',
}


def publisher(sp, label):
    if '/교육부_전북재게시/' in sp:
        return '교육부(전북특별자치도교육청 재게시)'
    if '/교육부/' in sp or 'C-T130-4-1' in sp:
        return '교육부'
    if 'K-T015-1-1' in sp:
        return '광주광역시교육청'
    if '/전남_연수원/' in sp:
        return '전라남도교육청교육연수원'
    if 'K-T051-' in sp:
        return '교육부·국가기초학력지원센터(전라남도교육청 게시)'
    return '전라남도교육청'


def safe(s, n=70):
    s = re.sub(r'\.(pdf|hwpx?|xlsm)$', '', s, flags=re.I)
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', ' ', s)
    s = re.sub(r'[★☆]', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' ._')
    return s[:n].strip()


def clean_ocr(t):
    """OCR 결과에서 한글·숫자·영단어가 없는 잡음 줄을 지운다."""
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

rows = []
for f in files:
    sha = f['sha256']; x = inv[sha]; d = CACHE + sha[:12] + '/'
    ids = [i for i in re.findall(r'T\d{3}', f['request_ids'])]
    # 첫 요청의 분류를 폴더로 쓴다
    cat = req[ids[0]]['category'] if ids and ids[0] in req else '요청 외 자료'
    title, orig = TITLE.get(f['file_id'], (safe(f['label'], 120), f['label']))
    body_parts = []; ocr_pages = []; missing = []; npages = 0
    if f['format'] == 'pdf':
        npages = int(f['pdf_pages'])
        for i in range(1, npages + 1):
            p = d + f'p{i:04d}.md'; po = d + f'p{i:04d}.ocr.md'
            if os.path.exists(p):
                t = open(p, encoding='utf-8').read().strip(); tag = ''
            elif os.path.exists(po):
                t = clean_ocr(open(po, encoding='utf-8').read()); ocr_pages.append(i)
                tag = ' (텍스트 층이 없어 OCR로 추출함. 오탈자와 순서 오류가 있을 수 있음)'
            else:
                missing.append(i); continue
            body_parts.append(f'<!-- 원문 {i}쪽{tag} -->\n\n{t}' if t else f'<!-- 원문 {i}쪽: 추출된 글자 없음 -->')
    else:
        p = d + 'whole.md'
        if os.path.exists(p):
            body_parts.append(open(p, encoding='utf-8').read().strip())
        else:
            missing.append('whole')
    if missing:
        rows.append(dict(f, category=cat, md_path='', md_bytes=0, ocr_pages=len(ocr_pages), status='미완료', missing=len(missing)))
        continue
    reqs = []
    for i in ids:
        if i in req:
            st = req[i]['claude_20260926_status']
            reqs.append(f"{i} {req[i]['requested_filename']} [{STATUS_SHORT.get(st, st)}]")
    fm = ['---',
          f'title: {yq(title)}',
          f'file_id: {f["file_id"]}',
          f'publisher: {yq(publisher(x["saved_path"], f["label"]))}',
          f'category: {yq(cat)}',
          f'original_format: {f["format"]}',
          f'original_file: {yq(orig)}',
          f'original_pages: {npages}' if npages else 'original_pages: ""',
          f'source_post: {yq(f["post_url"])}',
          f'source_file_url: {yq(f["file_url"])}',
          f'sha256: {sha}',
          'collected_on: 2026-09-26',
          'requests:' + ('' if reqs else ' []')] + [f'  - {yq(r)}' for r in reqs] + [
          f'ocr_pages: {len(ocr_pages)}',
          'license_note: "공공기관 게시 자료입니다. 다른 사람에게 배포하기 전에 원 게시물의 공공누리 유형과 이용 조건을 확인하십시오."',
          'conversion_note: "원문을 자동 변환한 파일입니다. 표·도식·이미지는 일부 손실될 수 있으므로, 중요한 수치와 규정은 원문과 대조하십시오."',
          '---', '']
    head = [f'# {title}', '',
            f'- 발행·게시: {publisher(x["saved_path"], f["label"])}',
            f'- 원문 파일: {orig} ({f["format"].upper()}' + (f', {npages}쪽' if npages else '') + ')',
            f'- 출처 게시물: {f["post_url"] or "게시물 주소 미확인(첨부 직접 주소)"}',
            '- 자동 변환본이므로 표와 그림은 원문과 대조하십시오.' + (f' 이 가운데 {len(ocr_pages)}쪽은 글자 층이 없는 이미지여서 OCR(문자 인식)로 추출했습니다.' if ocr_pages else ''),
            '']
    folder = OUT + '/' + safe(cat, 40)
    os.makedirs(folder, exist_ok=True)
    stem = safe(title)
    while len(stem.encode('utf-8')) > 150:
        stem = stem[:-1].rstrip()
    name = f'{f["file_id"].replace("N20260926-", "N")}_{stem}.md'
    path = folder + '/' + name
    text = '\n'.join(fm) + '\n'.join(head) + '\n' + '\n\n'.join(body_parts).strip() + '\n'
    open(path, 'w', encoding='utf-8').write(text)
    rows.append(dict(f, category=cat, md_path=os.path.relpath(path, OUT), md_bytes=len(text.encode()), ocr_pages=len(ocr_pages), status='완료', missing=0))

json.dump(rows, open(OUT + '/_변환기록.json', 'w'), ensure_ascii=False, indent=1)
import collections
done = [r for r in rows if r['status'] == '완료']
bycat = collections.OrderedDict()
for r in sorted(done, key=lambda r: (r['category'] == '요청 외 자료', r['category'], r['file_id'])):
    bycat.setdefault(r['category'], []).append(r)
tot = sum(r['md_bytes'] for r in done)
L = ['# 전남 교육자료 Markdown 변환본 목록', '',
     f'전라남도교육청 누리집 등에서 2026. 9. 26. 수집한 원문 {len(done)}개를 Markdown으로 변환했습니다. 원문 파일 1개가 Markdown 파일 1개입니다. 전체 크기는 약 {tot/1e6:.1f}MB입니다.', '',
     '## 사용 방법', '',
     '- Claude에서 프로젝트를 만든 뒤, 담당 업무에 필요한 폴더나 파일만 골라 프로젝트 지식에 올리십시오. 모든 파일을 한꺼번에 올리면 프로젝트 용량을 빠르게 채웁니다.',
     '- 각 파일 머리의 YAML 정보에 원문 제목, 출처 게시물 주소, SHA-256, 관련 요청 번호가 있습니다. 답변의 근거를 확인할 때 이 주소로 원문을 여십시오.',
     '- 본문에는 `<!-- 원문 12쪽 -->` 같은 쪽 표시가 있습니다. Claude에게 쪽 번호와 함께 인용하도록 요청하면 원문과 대조하기 쉽습니다.',
     '- 「OCR 쪽」이 있는 파일은 원문 PDF에 글자 층이 없어 문자 인식으로 추출한 부분입니다. 표와 도식이 많은 쪽은 순서가 섞이거나 글자가 틀릴 수 있으므로, 수치와 규정은 반드시 원문으로 확인하십시오.',
     '- 공공기관 게시 자료라도 공공누리 유형에 따라 출처 표시, 상업적 이용 금지, 변경 금지 조건이 붙습니다. 다른 사람에게 배포하기 전에 원 게시물의 이용 조건을 확인하십시오.',
     '- 같은 문서의 판이 여러 개 있으면(예: 「최종-」판과 일반판) 모두 변환했습니다. 파일 머리의 원문 파일명과 게시일을 보고 필요한 판만 고르십시오.', '',
     '## 품질 안내', '',
     '- 같은 문서를 HWP 원본과 PDF로 모두 받은 경우에는 HWP에서 변환한 파일이 더 정확합니다. 고교학점제 미리보기(워크북)는 N061(학생용)·N062(교사용)를, 교육공무직원 노무관리매뉴얼은 N059(모성보호 수정판)를 먼저 쓰십시오. 같은 워크북의 PDF 변환본(N099~N101, N113, N114)과 노무관리매뉴얼 PDF 변환본(N074)은 글꼴 정보가 깨져 있어서 여러 쪽을 OCR로 추출했습니다.',
     '- 다음 파일은 원문 PDF가 이미지이거나 글꼴 정보가 깨져 있어서 쪽의 80% 이상을 OCR로 추출했습니다. 문장은 대체로 읽을 수 있지만, 표와 도식은 순서가 섞입니다: ' + ', '.join(r['file_id'].replace('N20260926-', 'N') for r in done if r['pdf_pages'] and int(r['ocr_pages']) >= 0.8 * int(r['pdf_pages'])) + '.',
     '',
     '## 분류별 목록', '']
for cat, rs in bycat.items():
    L += [f'### {cat} ({len(rs)}개)', '', '| 파일 | 형식 | 쪽수 | OCR 쪽 | 관련 요청 | 크기 |', '|---|---|---:|---:|---|---:|']
    for r in rs:
        ids = ', '.join(re.findall(r'T\d{3}', r['request_ids'])) or '요청 외'
        L.append(f"| [{os.path.basename(r['md_path'])[:-3]}]({r['md_path'].replace(' ', '%20')}) | {r['format'].upper()} | {r['pdf_pages'] or ''} | {r['ocr_pages'] or ''} | {ids} | {r['md_bytes']/1000:.0f}KB |")
    L.append('')
L += ['## 변환하지 못한 자료', '', '- 이전 작업에서 받은 기존 71개 파일(D·A 계열)은 원본이 이번 작업 환경에 없어 변환하지 않았습니다. 원본을 제공하면 같은 방식으로 변환할 수 있습니다.', '']
open(OUT + '/00_목록.md', 'w', encoding='utf-8').write('\n'.join(L))
done = [r for r in rows if r['status'] == '완료']
print('완료', len(done), '미완료', len(rows) - len(done))
