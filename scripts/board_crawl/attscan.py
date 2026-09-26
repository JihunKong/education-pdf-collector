import json,re,os,time,subprocess,threading
from concurrent.futures import ThreadPoolExecutor
EX={'교육과정 > 학교교육과정','교육과정 > 학교자율시간(활동/과목)','교육자료 > 유아교육','장학/연수 > 국외연수'}
P=[json.loads(l) for l in open('posts_all.jsonl')]
u={}
for p in P:
    if p['board'] in EX or p['date']<'2024.01': continue
    u.setdefault(p['site']+p['nttSn'],p)
out='attnames.json'; res=json.load(open(out)) if os.path.exists(out) else {}
todo=[k for k in u if k not in res]; print('todo',len(todo),'of',len(u),flush=True)
lock=threading.Lock(); T0=time.time()
UA='education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'
def work(k):
    if time.time()-T0>150: return
    p=u[k]
    try: h=subprocess.run(['curl','-s','-m','20','-A',UA,p['url']],capture_output=True,timeout=25).stdout.decode('utf-8','replace')
    except Exception: return
    names=re.findall(r"fileAttachAddTxt\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+)[\"']",h)+re.findall(r"AddUploadedFile\(\s*'[^']*'\s*,\s*'([^']+)'\s*,\s*'([^']+)'",h)
    with lock: res[k]=[[a,b] for a,b in names]
with ThreadPoolExecutor(4) as ex: list(ex.map(work,todo))
json.dump(res,open(out,'w'),ensure_ascii=False)
print('done',len(res),'of',len(u))
