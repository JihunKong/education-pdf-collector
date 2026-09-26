"""법제처 국가법령정보 공동활용 API(DRF)로 법령·행정규칙을 받아 Markdown으로 바꾸는 모듈.

법령 본문은 저작권법 제7조에 따라 보호받지 않는 저작물이므로 자유롭게 이용할 수 있다.
"""
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://www.law.go.kr/DRF/'
UA = 'education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'


def get(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 + 3 * k)


def search(target, query, oc='test', rows=100):
    """target: law(법령), admrul(행정규칙). 결과를 dict 목록으로 돌려준다."""
    q = urllib.parse.quote(query)
    url = f'{BASE}lawSearch.do?OC={oc}&target={target}&type=XML&display={rows}&query={q}'
    root = ET.fromstring(get(url))
    tag = {'law': 'law', 'admrul': 'admrul'}[target]
    out = []
    for el in root.findall(tag):
        out.append({c.tag: (c.text or '').strip() for c in el})
    return out


def fetch(target, key, oc='test'):
    """target=law이면 key는 MST(법령일련번호), admrul이면 ID(행정규칙일련번호)."""
    k = 'MST' if target == 'law' else 'ID'
    return get(f'{BASE}lawService.do?OC={oc}&target={target}&{k}={key}&type=XML')


def clean(t):
    t = (t or '').replace('\r', '')
    t = re.sub(r'[ \t]+', ' ', t)
    return '\n'.join(l.strip() for l in t.split('\n')).strip()


def ymd(s):
    s = (s or '').strip()
    return f'{s[:4]}. {int(s[4:6])}. {int(s[6:8])}.' if re.fullmatch(r'\d{8}', s) else s


def yq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def render_law(xml_bytes, source_url, recent_addenda=3):
    """법령 XML을 조문 단위 Markdown으로 바꾼다. (meta, markdown)을 돌려준다."""
    root = ET.fromstring(xml_bytes)
    info = root.find('기본정보')
    g = lambda tag: clean(info.findtext(tag, '')) if info is not None else ''
    name = g('법령명_한글')
    meta = dict(name=name, law_id=g('법령ID'), kind=g('법종구분'), promulgated=g('공포일자'),
                promulgation_no=g('공포번호'), effective=g('시행일자'), revision=g('제개정구분'),
                ministry=g('소관부처'), abbrev=g('법령명약칭'))
    body = []
    for j in root.findall('./조문/조문단위'):
        kind = j.findtext('조문여부', '')
        content = clean(j.findtext('조문내용', ''))
        if kind == '전문':
            # 편·장·절·관 제목
            level = '##' if re.match(r'^제\d+(편|장)', content) else '###'
            body.append(f'{level} {content}')
            continue
        lines = [f'#### {content.split(")", 1)[0] + ")" if content.startswith("제") and ")" in content[:40] else content}']
        head_rest = content.split(')', 1)[1].strip() if content.startswith('제') and ')' in content[:40] else ''
        if head_rest:
            lines.append(head_rest)
        for hang in j.findall('항'):
            ht = clean(hang.findtext('항내용', ''))
            if ht:
                lines.append(ht)
            for ho in hang.findall('호'):
                lines.append('- ' + clean(ho.findtext('호내용', '')))
                for mok in ho.findall('목'):
                    lines.append('  - ' + clean(mok.findtext('목내용', '')))
        ref = clean(j.findtext('조문참고자료', ''))
        if ref:
            lines.append(f'<small>{ref}</small>')
        body.append('\n\n'.join(lines))
    # 별표
    tables = []
    for b in root.findall('./별표/별표단위'):
        title = clean(b.findtext('별표제목', ''))
        txt = clean(b.findtext('별표내용', ''))
        if title or txt:
            tables.append(f'### {title}\n\n```\n{txt}\n```' if txt else f'### {title}\n\n(별표 본문은 법제처 누리집에서 파일로 제공됨)')
    # 부칙: 최근 것 몇 개만
    add = [clean(a.findtext('부칙내용', '')) for a in root.findall('./부칙/부칙단위')]
    add = add[-recent_addenda:] if recent_addenda else add
    reason = clean(root.findtext('./제개정이유/제개정이유내용', ''))
    fm = ['---', f'title: {yq(name)}', f'law_kind: {yq(meta["kind"])}', f'law_id: {yq(meta["law_id"])}',
          f'promulgated: {yq(ymd(meta["promulgated"]))}', f'promulgation_no: {yq(meta["promulgation_no"])}',
          f'effective: {yq(ymd(meta["effective"]))}', f'revision: {yq(meta["revision"])}',
          f'ministry: {yq(meta["ministry"])}', f'source: {yq(source_url)}',
          'license_note: "법령 본문은 저작권법 제7조에 따라 보호받지 않는 저작물입니다. 효력이 있는 원문은 법제처 국가법령정보센터에서 확인하십시오."',
          '---', '']
    head = [f'# {name}', '', f'- 종류: {meta["kind"]} / 소관: {meta["ministry"]}',
            f'- 공포: {ymd(meta["promulgated"])} (제{meta["promulgation_no"]}호, {meta["revision"]}) / 시행: {ymd(meta["effective"])}',
            f'- 원문: {source_url}', '']
    parts = ['\n'.join(fm) + '\n'.join(head), '\n\n'.join(body)]
    if tables:
        parts.append('## 별표\n\n' + '\n\n'.join(tables))
    if add:
        parts.append('## 부칙(최근 %d개)\n\n' % len(add) + '\n\n'.join(add))
    if reason:
        parts.append('## 최근 제정·개정 이유\n\n' + reason)
    return meta, '\n\n'.join(parts).strip() + '\n'


def render_admrul(xml_bytes, source_url):
    """행정규칙 XML(훈령·예규·고시)을 Markdown으로 바꾼다."""
    root = ET.fromstring(xml_bytes)
    info = root.find('행정규칙기본정보')
    g = lambda tag: clean(info.findtext(tag, '')) if info is not None else ''
    name = g('행정규칙명')
    meta = dict(name=name, kind=g('행정규칙종류'), issued=g('발령일자'), issue_no=g('발령번호'),
                effective=g('시행일자'), ministry=g('소관부처명'), revision=g('제개정구분명'))
    body = []
    for t in root.findall('./조문내용'):
        txt = clean(t.text)
        if not txt:
            continue
        if re.match(r'^제\d+(편|장|절)', txt) and len(txt) < 60:
            body.append('## ' + txt)
        elif re.match(r'^제\d+조(의\d+)?\(', txt):
            title, rest = txt.split(')', 1)
            body.append(f'#### {title})\n\n{rest.strip()}' if rest.strip() else f'#### {title})')
        else:
            body.append(txt)
    add = [clean(a.text) for a in root.findall('./부칙/부칙내용')][-3:]
    tables = []
    for b in root.findall('./별표/별표단위'):
        title = clean(b.findtext('별표제목', ''))
        txt = clean(b.findtext('별표내용', ''))
        if title or txt:
            tables.append(f'### {title}\n\n```\n{txt}\n```' if txt else f'### {title}')
    fm = ['---', f'title: {yq(name)}', f'law_kind: {yq(meta["kind"])}', f'issued: {yq(ymd(meta["issued"]))}',
          f'issue_no: {yq(meta["issue_no"])}', f'effective: {yq(ymd(meta["effective"]))}',
          f'ministry: {yq(meta["ministry"])}', f'source: {yq(source_url)}',
          'license_note: "훈령·예규·고시 본문은 저작권법 제7조에 따라 보호받지 않는 저작물입니다. 효력이 있는 원문은 법제처 국가법령정보센터에서 확인하십시오."',
          '---', '']
    head = [f'# {name}', '', f'- 종류: {meta["kind"]} / 소관: {meta["ministry"]}',
            f'- 발령: {ymd(meta["issued"])} (제{meta["issue_no"]}호, {meta["revision"]}) / 시행: {ymd(meta["effective"])}',
            f'- 원문: {source_url}', '']
    parts = ['\n'.join(fm) + '\n'.join(head), '\n\n'.join(body)]
    if tables:
        parts.append('## 별표·서식\n\n' + '\n\n'.join(tables))
    if add:
        parts.append('## 부칙(최근)\n\n' + '\n\n'.join(add))
    return meta, '\n\n'.join(parts).strip() + '\n'


def cited_laws(md_text):
    """본문에 「」로 인용된 법령 이름과 횟수."""
    names = re.findall(r'「([^」]{2,40}?(?:법|법률|령|규칙|규정))」', md_text)
    out = {}
    for n in names:
        out[n] = out.get(n, 0) + 1
    return out
