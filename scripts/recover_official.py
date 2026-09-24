"""Continue the original target queue with two observed Jeonnam source URLs.
MOE transport success was established in run 35977100576; do not re-fetch it here.
Only encrypted output is retained by the workflow. No login or bypass is used.
"""
from pathlib import Path
import json
import time
from public_pdf_probe import fetch_one, MAX_PDF_BYTES, MAX_HTML_BYTES

TARGETS = [
    dict(id='T001_source_page',
         url='https://www.jne.go.kr/open/na/ntt/selectNttInfo.do?mi=551&nttSn=5135663',
         filename='T001_source_page.html', kind='html', limit=MAX_HTML_BYTES,
         note='Observed public post: 2025 high school credit system operation guide. This is source HTML, not a PDF.'),
    dict(id='T072_2026_personnel_candidate',
         url='https://www.jne.go.kr/upload/main/na/bbs_124/ntt_5168750/doc_e0cf1c96-3e8e-4d45-a364-6dcbb2beccf41771a8939b75126.pdf',
         filename='2026_교육공무원_인사실무_공식후보.pdf', kind='pdf', limit=MAX_PDF_BYTES,
         note='Previously observed official PDF URL. Request ID and bibliographic edition must be checked against the original queue; not approved for redistribution.'),
]

def main():
    out=Path('output')
    out.mkdir(exist_ok=True)
    results=[]
    for target in TARGETS:
        r=fetch_one(target,out)
        results.append(r)
        (out/'probe_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:r.get(k) for k in ('id','status','error_type','bytes')},ensure_ascii=False),flush=True)
        time.sleep(1)
    n=sum(r['status']=='saved' and r['kind']=='pdf' for r in results)
    (out/'SUMMARY.md').write_text(f'# Jeonnam recovery batch\n\nPDFs saved: {n}.\nHTML responses are source-discovery inputs only. Request matching, full PDF validation and distribution review remain pending.\n',encoding='utf-8')
    return 0 if n else 2

if __name__=='__main__':
    raise SystemExit(main())
