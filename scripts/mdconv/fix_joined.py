"""띄어쓰기가 사라진 쪽을 pdfminer 추출 결과로 바꾼다. pdfminer 결과가 한글을 90% 이상 담고 붙은 글자 비율이 낮을 때만 바꾼다."""
import json,re,os,time
from pdfminer.high_level import extract_text
inv=json.load(open('../inventory.json')); T0=time.time()
def jr(t):
    h=len(re.findall(r'[가-힣]',t)); l=sum(len(m) for m in re.findall(r'[가-힣]{15,}',t)); return h,(l/h if h else 0)
log=json.load(open('fix_joined_log.json')) if os.path.exists('fix_joined_log.json') else {}
for x in inv:
    if x['ext']!='pdf': continue
    d='cache/'+x['sha256'][:12]+'/'
    if not os.path.isdir(d): continue
    for f in sorted(os.listdir(d)):
        if not re.match(r'p\d{4}\.md$',f) or d+f in log: continue
        t=open(d+f,encoding='utf-8').read(); h,r=jr(t)
        if h<=100 or r<=0.08: continue
        if time.time()-T0>140: break
        pg=int(f[1:5])
        alt=extract_text('../epc_out/'+x['saved_path'],page_numbers=[pg-1])
        alt=re.sub(r'\n{3,}','\n\n',alt.replace('\x0c','')).strip()
        h2,r2=jr(alt)
        ok=h2>=0.9*h and r2<r/2
        if ok:
            open(d+f+'.orig','w').write(t); open(d+f,'w').write(alt)
        log[d+f]=dict(file=x['saved_path'][-50:],hangul=(h,h2),joined=(round(r,3),round(r2,3)),replaced=ok)
json.dump(log,open('fix_joined_log.json','w'),ensure_ascii=False,indent=1)
print('checked',len(log),'replaced',sum(v['replaced'] for v in log.values()))
for k,v in log.items():
    if not v['replaced']: print('kept',v)
