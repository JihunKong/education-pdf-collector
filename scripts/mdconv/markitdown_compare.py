"""변환본(ours)과 기준 텍스트(ref)를 파일별로 비교한다."""
import json,os,re,csv,collections
HOME=os.path.expanduser('~'); REF=HOME+'/mkcheck/ref/'; MD='/tmp/mdtest/'
rows=json.load(open(MD+'_변환기록.json'))
def body(t):
    t=t.split('\n---\n',1)[1] if t.startswith('---') else t
    return re.sub(r'<!--.*?-->','',t,flags=re.S)
def words(t): return re.findall(r'[가-힣]{2,}',t)
out=[]
for r in rows:
    ref_p=REF+r['sha256'][:12]+'.txt'
    if not os.path.exists(ref_p): continue
    ours=body(open(MD+r['md_path'],encoding='utf-8').read()); ref=open(ref_p,encoding='utf-8',errors='replace').read()
    wo,wr=collections.Counter(words(ours)),collections.Counter(words(ref))
    so,sr=set(wo),set(wr)
    # 기준 쪽 어휘가 변환본에 있는 비율(빈도 가중)
    rec=sum(c for w,c in wr.items() if w in so)/max(1,sum(wr.values()))
    prec=sum(c for w,c in wo.items() if w in sr)/max(1,sum(wo.values()))
    out.append(dict(file_id=r['file_id'],format=r['format'],pages=r['pdf_pages'],ocr_pages=r['ocr_pages'],
        hangul_ours=len(re.findall(r'[가-힣]',ours)),hangul_ref=len(re.findall(r'[가-힣]',ref)),
        ref_words_found_in_ours=round(rec,3),ours_words_found_in_ref=round(prec,3),
        fffd_ours=ours.count('�'),fffd_ref=ref.count('�'),
        tables_ours=len(re.findall(r'^\|[-|: ]+\|$',ours,re.M))+ours.count('<table>'),tables_ref=len(re.findall(r'^\|[-|: ]+\|$',ref,re.M)),
        ref_error=ref.startswith('__ERROR__'),md_path=r['md_path']))
csv.DictWriter(open(HOME+'/mkcheck/compare.csv','w',newline='',encoding='utf-8-sig'),fieldnames=list(out[0])).writerows([dict(zip(out[0],out[0]))]+out) if False else None
with open(HOME+'/mkcheck/compare.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out))
