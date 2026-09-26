"""HWP(pyhwp XML)·HWPX·XLSM 문서를 Markdown 블록으로 바꾸는 모듈."""
import re, subprocess, zipfile, os, html
import xml.etree.ElementTree as ET

ROMAN = re.compile(r'^\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ][\s.．]')


class Para:
    def __init__(self, text):
        self.text = text


class Table:
    def __init__(self):
        self.cells = []  # (row, col, rowspan, colspan, blocks)


def clean(t):
    t = t.replace(' ', ' ').replace('\r', '')
    t = re.sub(r'[ \t]+', ' ', t)
    return '\n'.join(l.strip() for l in t.split('\n')).strip()


# ---------- HWP (pyhwp hwp5proc xml) ----------
SKIP_HWP = {'FooterParagraphList', 'HeaderParagraphList', 'DocInfo', 'HwpSummaryInfo', 'PageDef',
            'ColumnsDef', 'FootnoteShape', 'PageBorderFill'}


def hwp_blocks(path, timeout=140):
    exe = os.path.expanduser('~/.local/bin/hwp5proc')
    r = subprocess.run([exe, 'xml', path], capture_output=True, timeout=timeout)
    root = ET.fromstring(r.stdout)
    body = root.find('.//BodyText')
    out = []
    walk_hwp_container(body if body is not None else root, out)
    return out


def hwp_blocks_from_xml(data):
    root = ET.fromstring(data)
    body = root.find('.//BodyText')
    out = []
    walk_hwp_container(body if body is not None else root, out)
    return out


def walk_hwp_container(el, out):
    for ch in el:
        if ch.tag in SKIP_HWP:
            continue
        if ch.tag == 'Paragraph':
            hwp_paragraph(ch, out)
        else:
            walk_hwp_container(ch, out)


def hwp_paragraph(p, out):
    buf = []

    def flush():
        t = clean(''.join(buf))
        if t:
            out.append(Para(t))
        buf.clear()

    def rec(el):
        for ch in el:
            tag = ch.tag
            if tag in SKIP_HWP:
                continue
            if tag == 'Text':
                buf.append(ch.text or '')
            elif tag == 'ControlChar':
                name = ch.get('name', '')
                if name == 'LINE_BREAK':
                    buf.append('\n')
                elif name == 'TAB':
                    buf.append(' ')
            elif tag == 'TableControl':
                flush()
                out.append(hwp_table(ch))
            elif tag == 'Paragraph':
                flush()
                hwp_paragraph(ch, out)
            else:
                rec(ch)
    rec(p)
    flush()


def hwp_table(tc):
    t = Table()
    body = tc.find('TableBody')
    if body is None:
        return t
    for row in body.findall('TableRow'):
        for cell in row.findall('TableCell'):
            blocks = []
            walk_hwp_container(cell, blocks)
            t.cells.append((int(cell.get('row', 0)), int(cell.get('col', 0)),
                            int(cell.get('rowspan', 1)), int(cell.get('colspan', 1)), blocks))
    return t


# ---------- HWPX ----------
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def hwpx_blocks(path):
    z = zipfile.ZipFile(path)
    names = sorted([n for n in z.namelist() if re.match(r'Contents/section\d+\.xml$', n)],
                   key=lambda n: int(re.findall(r'\d+', n)[-1]))
    out = []
    for n in names:
        root = ET.fromstring(z.read(n))
        for ch in root:
            if ch.tag == HP + 'p':
                hwpx_paragraph(ch, out)
    return out


def hwpx_paragraph(p, out):
    buf = []

    def flush():
        t = clean(''.join(buf))
        if t:
            out.append(Para(t))
        buf.clear()

    def text_of_t(t):
        s = [t.text or '']
        for c in t:
            tag = c.tag.replace(HP, '')
            if tag == 'lineBreak':
                s.append('\n')
            elif tag in ('tab', 'fwSpace', 'nbSpace'):
                s.append(' ')
            s.append(c.tail or '')
        return ''.join(s)

    def rec(el):
        for ch in el:
            tag = ch.tag.replace(HP, '')
            if tag in ('ctrl', 'header', 'footer', 'secPr', 'linesegarray'):
                continue
            if tag == 't':
                buf.append(text_of_t(ch))
            elif tag == 'tbl':
                flush()
                out.append(hwpx_table(ch))
            elif tag == 'p':
                flush()
                hwpx_paragraph(ch, out)
            else:
                rec(ch)
    rec(p)
    flush()


def hwpx_table(tbl):
    t = Table()
    for tr in tbl.findall(HP + 'tr'):
        for tc in tr.findall(HP + 'tc'):
            addr = tc.find(HP + 'cellAddr'); span = tc.find(HP + 'cellSpan')
            blocks = []
            sub = tc.find(HP + 'subList')
            for p in (sub if sub is not None else tc).findall(HP + 'p'):
                hwpx_paragraph(p, blocks)
            t.cells.append((int(addr.get('rowAddr', 0)) if addr is not None else 0,
                            int(addr.get('colAddr', 0)) if addr is not None else 0,
                            int(span.get('rowSpan', 1)) if span is not None else 1,
                            int(span.get('colSpan', 1)) if span is not None else 1, blocks))
    return t


# ---------- 렌더링 ----------
def blocks_text(blocks, sep='<br>'):
    parts = []
    for b in blocks:
        if isinstance(b, Para):
            parts.append(b.text.replace('\n', sep))
        else:
            parts.append(render_table(b, inline=True))
    return sep.join(p for p in parts if p)


def has_text(blocks):
    for b in blocks:
        if isinstance(b, Para):
            if b.text.strip():
                return True
        elif any(has_text(x[4]) for x in b.cells):
            return True
    return False


def prune_empty_rows(t):
    """모든 칸이 빈 행을 지운다. 위 행의 병합 칸이 걸쳐 있는 행은 남긴다."""
    covered = set()
    for r, c, rs, cs, b in t.cells:
        if rs > 1:
            covered.update(range(r + 1, r + rs))
    rows = {}
    for x in t.cells:
        rows.setdefault(x[0], []).append(x)
    empty = {r for r, xs in rows.items()
             if r not in covered and all(x[2] == 1 and not has_text(x[4]) for x in xs)}
    if empty:
        t.cells = [(r - sum(1 for e in empty if e < r), c, rs, cs, b)
                   for r, c, rs, cs, b in t.cells if r not in empty]


def render_table(t, inline=False):
    if not t.cells:
        return ''
    prune_empty_rows(t)
    if not t.cells:
        return ''
    filled = [x for x in t.cells if has_text(x[4])]
    if not inline and len(filled) == 1:
        body = render_blocks(filled[0][4])
        return '\n'.join('> ' + l if l else '>' for l in body.split('\n'))
    if not filled:
        return ''
    nrow = max(r + rs for r, c, rs, cs, b in t.cells)
    ncol = max(c + cs for r, c, rs, cs, b in t.cells)
    nested = any(not isinstance(x, Para) for *_, b in t.cells for x in b)
    spans = any(rs > 1 or cs > 1 for r, c, rs, cs, b in t.cells)
    if not inline and len(t.cells) == 1:
        # 1칸짜리 표는 글상자이므로 인용 블록으로 쓴다
        body = render_blocks(t.cells[0][4])
        return '\n'.join('> ' + l if l else '>' for l in body.split('\n'))
    if not inline and ncol == 1 and not nested:
        return '\n\n'.join(render_blocks(b) for *_, b in sorted(t.cells))
    if not spans and not nested and not inline:
        grid = [[''] * ncol for _ in range(nrow)]
        for r, c, rs, cs, b in t.cells:
            grid[r][c] = blocks_text(b).replace('|', '\\|')
        lines = ['| ' + ' | '.join(grid[0]) + ' |', '|' + '---|' * ncol]
        lines += ['| ' + ' | '.join(row) + ' |' for row in grid[1:]]
        return '\n'.join(lines)
    rows = {}
    for r, c, rs, cs, b in sorted(t.cells):
        rows.setdefault(r, []).append((c, rs, cs, b))
    h = ['<table>']
    for r in sorted(rows):
        h.append('<tr>' + ''.join(
            '<td' + (f' rowspan="{rs}"' if rs > 1 else '') + (f' colspan="{cs}"' if cs > 1 else '') + '>'
            + blocks_text(b) + '</td>' for c, rs, cs, b in rows[r]) + '</tr>')
    h.append('</table>')
    return ''.join(h) if inline else '\n'.join(h)


def render_blocks(blocks):
    out = []
    for b in blocks:
        if isinstance(b, Para):
            txt = b.text
            if ROMAN.match(txt) and len(txt) < 60 and not re.search(r'[\s.·]\d{1,3}$', txt):
                txt = '## ' + txt
            out.append(txt.replace('\n', '  \n'))
        else:
            s = render_table(b)
            if s:
                out.append(s)
    return '\n\n'.join(out)


# ---------- XLSM ----------
def xlsx_markdown(path, max_rows=3000):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = ['' if v is None else str(v).strip().replace('\n', '<br>').replace('|', '\\|') for v in row]
            if any(vals):
                rows.append(vals)
            if len(rows) >= max_rows:
                break
        if not rows:
            continue
        used = [i for i in range(max(len(r) for r in rows)) if any(i < len(r) and r[i] for r in rows)]
        rows = [[r[i] if i < len(r) else '' for i in used] for r in rows]
        parts.append(f'## 시트: {ws.title}\n')
        parts.append('| ' + ' | '.join(rows[0]) + ' |')
        parts.append('|' + '---|' * len(used))
        parts += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
        parts.append('')
    return '\n'.join(parts)
