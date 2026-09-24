"""Use observed MOE attachment URLs; retain only encrypted results in CI.
The failed Incheon response is diagnostic HTML, never counted as a PDF.
"""
from pathlib import Path
import json
import time
from public_pdf_probe import fetch_one, MAX_PDF_BYTES, MAX_HTML_BYTES

SOURCE = 'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=316&boardSeq=105372&lev=0&m=0302&opType=N&page=1&s=moe&searchType=null&statusYN=W'
ATTACHMENTS = [
    ('T158_2026_primary', '20b6e362275e20aefc61857e4af63872', '2026 학교생활기록부 기재요령(초등학교).pdf'),
    ('extra_2026_middle', '4ad0d9bae480b48e1b9b3de0592f955b', '2026 학교생활기록부 기재요령(중학교).pdf'),
    ('extra_2026_high', '6668402ed462e43bd1ff70123359bf50', '2026 학교생활기록부 기재요령(고등학교).pdf'),
]

def main():
    out = Path('output')
    out.mkdir(exist_ok=True)
    results = []
    for docid, seq, filename in ATTACHMENTS:
        target = dict(id=docid, url=f'https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq={seq}&m=0302&s=moe',
                      filename=filename, kind='pdf', limit=MAX_PDF_BYTES,
                      note='Official attachment link observed on MOE post 105372. Edition validation pending; redistribution not approved.')
        r = fetch_one(target, out)
        r['source_page'] = SOURCE
        results.append(r)
        (out / 'probe_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:r.get(k) for k in ('id','status','error_type','bytes')}, ensure_ascii=False), flush=True)
        time.sleep(1)
    diagnostic = dict(id='incheon_html_diagnostic', url='https://www.ice.go.kr/upload/ice/na/bbs_1630/2026/02/54805c6beb01532ef8ecb9b71a3155ed.pdf',
                      filename='incheon_response_diagnostic.html', kind='html', limit=MAX_HTML_BYTES,
                      note='Inspect earlier 77-byte HTML response; not a source PDF and not counted as collected.')
    results.append(fetch_one(diagnostic, out))
    (out / 'probe_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    count = sum(r['status']=='saved' and r['kind']=='pdf' for r in results)
    (out / 'SUMMARY.md').write_text(f'# Official attachment transport test\n\nPDFs saved: {count}/3.\n\nSource: {SOURCE}\n\nFull PDF parsing and source/edition review remain required. Redistribution is not approved.\n', encoding='utf-8')
    return 0 if count else 2

if __name__ == '__main__':
    raise SystemExit(main())
