import json,os,sys,time
from lister import page
boards=json.load(open('boards.json')); out='posts_all.jsonl'; prog='progress.json'
P=json.load(open(prog)) if os.path.exists(prog) else {}
t0=time.time()
for b in boards:
    k=b['site']+'/'+b['mi']
    st=P.get(k,{'page':0,'done':False})
    while not st['done']:
        if time.time()-t0>160: json.dump(P,open(prog,'w')); print('STOP'); sys.exit(3)
        p=st['page']+1
        try: rows=page(b['site'],b['mi'],p,50,b['bbsId'])
        except Exception as e: rows=[]
        with open(out,'a') as f:
            for r in rows: r['board']=b['board']; r['site']=b['site']; r['mi']=b['mi']; r['bbsId']=b['bbsId']; f.write(json.dumps(r,ensure_ascii=False)+'\n')
        dated=[r['date'] for r in rows if r['date']]
        st['page']=p
        if not rows or (dated and max(dated)<'2023.07.01') or p>=60: st['done']=True
        P[k]=st
    json.dump(P,open(prog,'w'))
print('ALL_DONE')
