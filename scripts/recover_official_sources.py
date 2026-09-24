"""Try verified official attachment links, not guessed identifiers.
Public code only; output is encrypted by the following workflow step.
"""
from pathlib import Path
import json
import sys
import time
from public_pdf_probe import fetch_one, allowed_url

SOURCES = [
    {
        'id': 'T158_moe_primary_2026',
        'url': 'https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq=20b6e362275e20aefc61857e4af63872&m=0302&s=moe',
        'filename': '2026_school_record_primary_MOE.pdf',
        'kind': 'pdf', 'limit': 9 * 1024 * 1024,
        'note': '2026 primary school record guide. Explicit attachment link from MOE post 105372. Edition matching pending. KOGL type 4; no public redistribution.',
        'source_page': 'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=316&boardSeq=105372&lev=0&m=0302&opType=N&page=1&s=moe&searchType=null&statusYN=W',
    },
    {
        'id': 'EXTRA_moe_high_2026',
        'url': 'https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq=6668402ed462e43bd1ff70123359bf50&m=0302&s=moe',
        'filename': '2026_school_record_high_MOE.pdf',
        'kind': 'pdf', 'limit': 9 * 1024 * 1024,
        'note': '2026 high school record guide. Additional document, NOT replacement for requested 2025 edition. KOGL type 4; no public redistribution.',
        'source_page': 'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=316&boardSeq=105372&lev=0&m=0302&opType=N&page=1&s=moe&searchType=null&statusYN=W',
    },
    {
        'id': 'CANDIDATE_jne_student_workbook_2025',
        'url': 'https://www.jne.go.kr/upload/parents/na/bbs_514/ntt_5143611/doc_41992165-6d10-44dc-9797-06fcf5e5fd4a1745a8312b12892.pdf',
        'filename': '2025_JN_credit_workbook_student_candidate.pdf',
        'kind': 'pdf', 'limit': 9 * 1024 * 1024,
        'note': 'Official parent-center repost, April 28 2025. Student workbook candidate, not verified to match final(0501) or 16-jeol variants. Redistribution not reviewed.',
        'source_page': 'https://www.jne.go.kr/parents/na/ntt/selectNttInfo.do?mi=1208&nttSn=5143611',
    },
]

def main():
    out = Path('output'); out.mkdir(exist_ok=True)
    assert len(SOURCES) == 3 and all(allowed_url(x['url']) for x in SOURCES)
    results=[]
    for target in SOURCES:
        record=fetch_one(target,out)
        record['source_page']=target['source_page']
        results.append(record)
        (out/'probe_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:record.get(k) for k in ['id','status','http_status','content_type','bytes','error_type','error']},ensure_ascii=False),flush=True)
        time.sleep(2)
    saved=sum(x['status']=='saved' for x in results)
    (out/'SUMMARY.md').write_text(f'# Official attachment transport test\n\nSaved PDF files: {saved}/3.\nFull parsing, cover and edition checks are pending at recipient. No target completion or redistribution approval implied.\n',encoding='utf-8')
    return 0 if saved else 2

if __name__=='__main__':
    sys.exit(main())
