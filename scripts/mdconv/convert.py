"""수집 파일을 쪽·파일 단위로 Markdown 캐시에 변환한다. 시간 예산 안에서 끊어 실행하고 다시 실행하면 이어서 한다.
사용법: python3 convert.py [예산초]
"""
import json, os, sys, time, subprocess, tempfile
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

HOME = os.path.expanduser('~')
BASE = HOME + '/epc_out/'
CACHE = HOME + '/mdconv/cache/'
BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 150
os.environ['TESSDATA_PREFIX'] = HOME + '/tessdata'
os.environ['OMP_THREAD_LIMIT'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'


def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


def ocr_page(page):
    pix = page.get_pixmap(dpi=200)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        png = f.name
    pix.save(png)
    try:
        r = subprocess.run(['tesseract', png, '-', '-l', 'kor+eng', '--psm', '4'],
                           capture_output=True, text=True, timeout=120)
        txt = r.stdout
    finally:
        os.unlink(png)
    lines = [l.rstrip() for l in txt.splitlines()]
    out, blank = [], 0
    for l in lines:
        if l.strip():
            out.append(l.strip()); blank = 0
        else:
            blank += 1
            if blank == 1:
                out.append('')
    return '\n'.join(out).strip()


def pdf_page(path, pno, dest):
    import pymupdf, pymupdf4llm
    doc = pymupdf.open(path)
    page = doc[pno]
    raw = page.get_text().strip()
    if len(raw) >= 30:
        md = pymupdf4llm.to_markdown(doc, pages=[pno], use_ocr=False, header=False, footer=False,
                                     show_progress=False, ignore_images=True)
        atomic_write(dest, md.strip())
    else:
        has_img = bool(page.get_images()) or bool(page.get_drawings())
        md = ocr_page(page) if has_img else raw
        atomic_write(dest.replace('.md', '.ocr.md') if has_img else dest, md)
    return dest


def whole_file(path, ext, dest):
    sys.path.insert(0, HOME + '/mdconv')
    import hwpmd
    if ext == 'hwp':
        md = hwpmd.render_blocks(hwpmd.hwp_blocks(path))
    elif ext == 'hwpx':
        md = hwpmd.render_blocks(hwpmd.hwpx_blocks(path))
    elif ext in ('xlsm', 'xlsx'):
        md = hwpmd.xlsx_markdown(path)
    else:
        raise ValueError(ext)
    atomic_write(dest, md)
    return dest


def run(unit):
    kind, path, arg, dest = unit
    try:
        if kind == 'pdf':
            return pdf_page(path, arg, dest)
        return whole_file(path, arg, dest)
    except Exception as e:
        atomic_write(dest.replace('.md', '.err'), repr(e))
        return 'ERR ' + dest


def units():
    import pymupdf
    inv = json.load(open(HOME + '/inventory.json'))
    skip = set(open(HOME + '/mdconv/skip_shas.txt').read().split()) if os.path.exists(HOME + '/mdconv/skip_shas.txt') else set()
    inv = [x for x in inv if x['sha256'] not in skip]
    todo = []
    for x in inv:
        d = CACHE + x['sha256'][:12] + '/'
        p = BASE + x['saved_path']
        if x['ext'] == 'pdf':
            n = pymupdf.open(p).page_count
            for i in range(n):
                dest = d + f'p{i + 1:04d}.md'
                if not any(os.path.exists(dest.replace('.md', s)) for s in ('.md', '.ocr.md', '.err')):
                    todo.append(('pdf', p, i, dest))
        else:
            dest = d + 'whole.md'
            if not (os.path.exists(dest) or os.path.exists(d + 'whole.err')):
                todo.append(('file', p, x['ext'], dest))
    # 무거운 파일 단위 작업을 먼저 넣는다
    low = {}
    if os.path.exists(HOME + '/mdconv/lowtext.json'):
        for sp, pages in json.load(open(HOME + '/mdconv/lowtext.json')):
            low[BASE + sp] = set(pages)
    todo.sort(key=lambda u: (u[0] == 'pdf', u[0] == 'pdf' and u[2] in low.get(u[1], ()), u[1], u[2] if u[0] == 'pdf' else 0))
    return todo


if __name__ == '__main__':
    T0 = time.time()
    todo = units()
    print('남은 작업', len(todo), flush=True)
    done = err = 0
    with ProcessPoolExecutor(4) as ex:
        it = iter(todo); running = set()
        while True:
            while len(running) < 4 and time.time() - T0 < BUDGET:
                u = next(it, None)
                if u is None:
                    break
                running.add(ex.submit(run, u))
            if not running:
                break
            fin, running = wait(running, timeout=max(1, BUDGET + 12 - (time.time() - T0)), return_when=FIRST_COMPLETED)
            for f in fin:
                r = f.result()
                if str(r).startswith('ERR'):
                    err += 1
                else:
                    done += 1
            if time.time() - T0 > BUDGET + 12:
                break
    print('완료', done, '오류', err, '경과', round(time.time() - T0), '초', flush=True)
    os._exit(0)
