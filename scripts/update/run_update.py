"""교육자료 자동 갱신: 법령 개정 반영 → 새 판 검색 → 내려받기 → Markdown 변환 → 폴더 반영.

Mac의 Cowork 셸에서 실행한다. 한 번 실행할 때 약 150초만 일하고 끝나므로, 'ALL_DONE'이 나올 때까지 되풀이해 실행한다.
작업 상태는 사용자 폴더(md_변환도구/자동갱신/_state)에 남기므로, 세션이 바뀌어도 이어서 할 수 있다.

사용법: python3 run_update.py "<교육자료 PDF 수집 폴더>"
"""
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time

U = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/mnt/AILEVELUP/교육자료 PDF 수집')
TOOLS = os.path.join(U, 'md_변환도구')
AUTO = os.path.join(TOOLS, '자동갱신')
ST_DIR = os.path.join(AUTO, '_state')
REAL_HOME = os.path.expanduser('~')
WORK = os.path.join(REAL_HOME, '_upd')
STAMP = datetime.date.today().strftime('%Y%m%d')
STATE_P = os.path.join(ST_DIR, f'run_{STAMP}.json')
BUDGET = 140
T0 = time.time()
os.makedirs(ST_DIR, exist_ok=True)
st = json.load(open(STATE_P)) if os.path.exists(STATE_P) else {'done': [], 'log': []}


def save():
    json.dump(st, open(STATE_P, 'w'), ensure_ascii=False, indent=1)


def log(msg):
    print(msg, flush=True)
    st['log'].append(time.strftime('%H:%M:%S ') + msg)
    save()


def env():
    e = dict(os.environ)
    e['HOME'] = WORK
    e['PYTHONUSERBASE'] = os.path.join(REAL_HOME, '.local')
    e['TESSDATA_PREFIX'] = os.path.join(WORK, 'tessdata')
    e['LAW_BUDGET'] = str(BUDGET)
    return e


def run(cmd, cwd=None, timeout=165):
    r = subprocess.run(cmd, cwd=cwd, env=env(), capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or '') + (r.stderr or '')
    return r.returncode, '\n'.join(l for l in out.splitlines() if 'onnxruntime' not in l and 'cpuinfo' not in l)


def step(name):
    return name not in st['done']


def finish(name):
    st['done'].append(name)
    save()


def budget_left():
    return BUDGET - (time.time() - T0)


# 1. 준비: 패키지, 작업 폴더, 캐시·상태 복사
if step('setup'):
    need = []
    for mod, pkg in (('pymupdf4llm', 'pymupdf4llm'), ('hwp5', 'pyhwp'), ('pdfminer', 'pdfminer.six'), ('openpyxl', 'openpyxl')):
        if subprocess.run([sys.executable, '-c', f'import {mod}'], capture_output=True).returncode:
            need.append(pkg)
    if need:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', '-q'] + need, timeout=160)
    os.makedirs(WORK, exist_ok=True)
    if not os.path.exists(os.path.join(WORK, '.local')):
        os.symlink(os.path.join(REAL_HOME, '.local'), os.path.join(WORK, '.local'))
    td = os.path.join(WORK, 'tessdata')
    os.makedirs(td, exist_ok=True)
    for f in glob.glob('/usr/share/tesseract-ocr/*/tessdata/*.traineddata') + glob.glob(os.path.join(TOOLS, 'tessdata', '*.traineddata')):
        shutil.copy2(f, td)
    for d in glob.glob('/usr/share/tesseract-ocr/*/tessdata/*configs'):
        shutil.copytree(d, os.path.join(td, os.path.basename(d)), dirs_exist_ok=True)
    # 캐시
    mc = os.path.join(WORK, 'mdconv')
    os.makedirs(mc, exist_ok=True)
    if os.path.isdir(os.path.join(TOOLS, '_cache')):
        shutil.copytree(os.path.join(TOOLS, '_cache'), os.path.join(mc, 'cache'), dirs_exist_ok=True)
    for f in ('convert.py', 'hwpmd.py', 'build_md.py', 'reocr_bad.py', 'fix_joined.py'):
        shutil.copy2(os.path.join(AUTO, 'mdconv', f), mc)
    for f in ('new_manifest.json', 'lowtext.json', 'skip_shas.txt'):
        p = os.path.join(TOOLS, '_cache_meta', f)
        if os.path.exists(p):
            shutil.copy2(p, mc)
    # 같은 문서의 PDF·HWP가 함께 있으면 HWP만 변환한다(변환 목록의 skip_alt)
    man_p = os.path.join(mc, 'new_manifest.json')
    skip_alt = json.load(open(man_p)).get('skip_alt', []) if os.path.exists(man_p) else []
    open(os.path.join(mc, 'skip_shas.txt'), 'w').write('\n'.join(skip_alt))
    # 수집 상태와 원문(심볼릭 링크)
    eo = os.path.join(WORK, 'epc_out')
    os.makedirs(os.path.join(eo, 'pdfs'), exist_ok=True)
    shutil.copy2(os.path.join(U, 'collected', 'state.json'), os.path.join(eo, 'state.json'))
    for p in glob.glob(os.path.join(U, 'collected', 'pdfs', '*', '*')):
        rel = os.path.relpath(p, os.path.join(U, 'collected'))
        q = os.path.join(eo, rel)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        if not os.path.lexists(q):
            os.symlink(p, q)
    shutil.copytree(os.path.join(AUTO, 'epc'), os.path.join(WORK, 'epc'), dirs_exist_ok=True)
    shutil.copytree(os.path.join(AUTO, 'laws'), os.path.join(WORK, 'laws'), dirs_exist_ok=True)
    shutil.copytree(os.path.join(AUTO, 'update'), os.path.join(WORK, 'update'), dirs_exist_ok=True)
    lo = os.path.join(TOOLS, '법령', '_out')
    shutil.copytree(lo, os.path.join(WORK, 'laws_out'), dirs_exist_ok=True)
    rc, out = run([sys.executable, os.path.join(WORK, 'update', 'build_inv.py')])
    rc, out = run([sys.executable, os.path.join(WORK, 'update', 'verify_pages.py')], timeout=160)
    log('준비 완료 ' + out.strip()[-200:])
    finish('setup')

# 2. 법령 개정 확인
if step('laws') and budget_left() > 30:
    rc, out = run([sys.executable, 'fetch_laws.py', 'law_list.json', os.path.join(WORK, 'laws_out')], cwd=os.path.join(WORK, 'laws'))
    log('법령: ' + out.strip()[-600:])
    if rc == 0:
        run([sys.executable, 'law_index.py', os.path.join(WORK, 'laws_out')], cwd=os.path.join(WORK, 'laws'))
        finish('laws')

# 3. 현재 목록을 만들고 새 판 검색
build_dir = os.path.join(WORK, 'md_build')
if step('build0') and budget_left() > 40:
    shutil.rmtree(build_dir, ignore_errors=True)
    rc, out = run([sys.executable, os.path.join(WORK, 'mdconv', 'build_md.py'), build_dir,
                   os.path.join(U, sorted(glob.glob(os.path.join(U, '수집파일_*개_*.csv')))[-1]),
                   os.path.join(U, 'requested_160_갱신_20260926.csv'), os.path.join(WORK, 'laws_out')])
    log('현재 목록: ' + out.strip()[-200:])
    finish('build0')
cand_p = os.path.join(ST_DIR, f'candidates_{STAMP}.json')
if step('scan') and budget_left() > 30:
    rc, out = run([sys.executable, os.path.join(WORK, 'update', 'editions.py'), 'scan', os.path.join(build_dir, '_변환기록.json'), cand_p, str(int(budget_left() - 10))])
    log('새 판 검색: ' + out.strip()[-800:])
    if rc == 0:
        run([sys.executable, os.path.join(WORK, 'update', 'editions.py'), 'jobs', cand_p, os.path.join(WORK, 'jobs')])
        finish('scan')

# 4. 새 판 내려받기
if step('fetch') and budget_left() > 30 and 'scan' in st['done']:
    jobs = os.path.join(WORK, 'jobs')
    cj = json.load(open(os.path.join(jobs, 'collector_jobs.json')))
    gj = json.load(open(os.path.join(jobs, 'goe_selected.json')))
    done_c = done_g = True
    if cj:
        rc, out = run([sys.executable, 'run_chunk.py', os.path.join(jobs, 'collector_jobs.json'), str(int(budget_left() - 15)), os.path.join(WORK, 'epc_out')], cwd=os.path.join(WORK, 'epc'))
        done_c = 'ALL_DONE' in out
        log('수집기: ' + out.strip()[-400:])
    if gj and budget_left() > 30:
        rc, out = run([sys.executable, os.path.join(WORK, 'update', 'goe_download.py'), os.path.join(jobs, 'goe_selected.json'), '경기도교육청', 'U' + STAMP + 'G'])
        done_g = 'pages done %d of %d' % (len(gj), len(gj)) in out
        log('경기도교육청: ' + out.strip()[-400:])
    if done_c and done_g:
        # 새로 받은 파일을 변환 목록에 넣는다
        s = json.load(open(os.path.join(WORK, 'epc_out', 'state.json')))['records']
        man_p = os.path.join(WORK, 'mdconv', 'new_manifest.json')
        man = json.load(open(man_p)) if os.path.exists(man_p) else {'convert': [], 'skip_alt': []}
        new = [v['sha256'] for v in s.values() if str(v.get('id', '')).startswith('U' + STAMP) and v.get('status') == 'downloaded']
        man['convert'] = sorted(set(man['convert']) | set(new))
        json.dump(man, open(man_p, 'w'))
        run([sys.executable, os.path.join(WORK, 'update', 'build_inv.py')])
        run([sys.executable, os.path.join(WORK, 'update', 'verify_pages.py')], timeout=160)
        st['new_files'] = len(new)
        log(f'새로 받은 파일 {len(new)}개')
        finish('fetch')

# 5. 변환
if step('convert') and budget_left() > 40 and 'fetch' in st['done']:
    rc, out = run([sys.executable, os.path.join(WORK, 'mdconv', 'convert.py'), str(int(budget_left() - 25))], cwd=os.path.join(WORK, 'mdconv'))
    log('변환: ' + out.strip()[-200:])
    if '남은 작업 0' in out:
        finish('convert')

# 5-1. 글꼴이 깨진 쪽은 OCR로, 띄어쓰기가 사라진 쪽은 pdfminer로 다시 뽑는다
if step('repair') and budget_left() > 40 and 'convert' in st['done']:
    rc, out = run([sys.executable, os.path.join(WORK, 'mdconv', 'reocr_bad.py'), str(int(budget_left() - 25))], cwd=os.path.join(WORK, 'mdconv'))
    log('깨진 쪽 OCR: ' + out.strip()[-200:])
    if rc == 0:
        rc2, out2 = run([sys.executable, os.path.join(WORK, 'mdconv', 'fix_joined.py')], cwd=os.path.join(WORK, 'mdconv'))
        log('띄어쓰기 복원: ' + out2.strip()[-200:])
        finish('repair')

# 6. 새 트리를 만들고 사용자 폴더에 반영
if step('publish') and budget_left() > 50 and 'repair' in st['done'] and 'laws' in st['done']:
    shutil.rmtree(build_dir, ignore_errors=True)
    rc, out = run([sys.executable, os.path.join(WORK, 'mdconv', 'build_md.py'), build_dir,
                   os.path.join(U, sorted(glob.glob(os.path.join(U, '수집파일_*개_*.csv')))[-1]),
                   os.path.join(U, 'requested_160_갱신_20260926.csv'), os.path.join(WORK, 'laws_out')])
    log('새 목록: ' + out.strip()[-200:])
    trash = os.path.join(U, '_to_delete', f'md_갱신전_{STAMP}')
    rc, out = run([sys.executable, os.path.join(WORK, 'update', 'sync_tree.py'), build_dir, os.path.join(U, 'md'), trash])
    log('폴더 반영: ' + out.strip())
    # 교사 배포용 ZIP을 다시 만든다(파일 이름은 UTF-8로 기록)
    import zipfile
    zp = os.path.join(WORK, 'md.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(build_dir):
            for f in sorted(fs):
                z.write(os.path.join(dp, f), '교육자료_MD변환본/' + os.path.relpath(os.path.join(dp, f), build_dir))
    shutil.copy2(zp, os.path.join(U, '교육자료_MD변환본_최신.zip'))
    # 원문·상태·캐시·법령 상태를 사용자 폴더에 되돌려 둔다
    for p in glob.glob(os.path.join(WORK, 'epc_out', 'pdfs', '*', '*')):
        if not os.path.islink(p):
            q = os.path.join(U, 'collected', os.path.relpath(p, os.path.join(WORK, 'epc_out')))
            os.makedirs(os.path.dirname(q), exist_ok=True)
            if not os.path.exists(q):
                shutil.copy2(p, q)
    shutil.copy2(os.path.join(WORK, 'epc_out', 'state.json'), os.path.join(U, 'collected', 'state.json'))
    shutil.copytree(os.path.join(WORK, 'mdconv', 'cache'), os.path.join(TOOLS, '_cache'), dirs_exist_ok=True)
    os.makedirs(os.path.join(TOOLS, '_cache_meta'), exist_ok=True)
    for f in ('new_manifest.json', 'lowtext.json'):
        p = os.path.join(WORK, 'mdconv', f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(TOOLS, '_cache_meta', f))
    rc, out = run([sys.executable, os.path.join(WORK, 'update', 'sync_tree.py'), os.path.join(WORK, 'laws_out'),
                   os.path.join(TOOLS, '법령', '_out'), os.path.join(U, '_to_delete', f'법령상태_갱신전_{STAMP}')])
    finish('publish')

# 7. 보고서
if step('report') and 'publish' in st['done']:
    cand = json.load(open(cand_p)) if os.path.exists(cand_p) else {'candidates': []}
    rep = [f'# 교육자료 자동 갱신 보고 ({STAMP})', '', f'- 새 판 후보 {len(cand["candidates"])}건, 새로 받은 파일 {st.get("new_files", 0)}개', '']
    for c in cand['candidates']:
        rep.append(f"- [{c['group']}] {c['old_fid']} {c['old_title']} → {c['new_title']} ({c['date']}) {c['url']}")
    rep += ['', '## 실행 기록', ''] + [f'- {l}' for l in st['log']]
    open(os.path.join(ST_DIR, f'report_{STAMP}.md'), 'w').write('\n'.join(rep))
    finish('report')
    print('ALL_DONE')
    print('\n'.join(rep[:40]))
else:
    print('남은 단계:', [s for s in ('setup', 'laws', 'build0', 'scan', 'fetch', 'convert', 'repair', 'publish', 'report') if s not in st['done']])
    sys.exit(3)
