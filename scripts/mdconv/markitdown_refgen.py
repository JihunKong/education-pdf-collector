"""대조용 기준 텍스트를 만든다: PDF·XLSM은 markitdown, HWP는 hwp5txt, HWPX는 섹션 XML의 hp:t 글자."""
import json,os,subprocess,time,zipfile,re,sys
from concurrent.futures import ThreadPoolExecutor
HOME=os.path.expanduser('~'); REF=HOME+'/mkcheck/ref/'
inv=json.load(open(HOME+'/inventory.json')); T0=time.time(); BUDGET=float(sys.argv[1]) if len(sys.argv)>1 else 140
def work(x):
    out=REF+x['sha256'][:12]+'.txt'
    if os.path.exists(out) or time.time()-T0>BUDGET: return
    p=HOME+'/epc_out/'+x['saved_path']
    try:
        if x['ext'] in ('pdf','xlsm'):
            txt=subprocess.run(['markitdown',p],capture_output=True,text=True,timeout=160).stdout
        elif x['ext']=='hwp':
            txt=subprocess.run([HOME+'/.local/bin/hwp5txt',p],capture_output=True,text=True,timeout=160).stdout
        else:
            z=zipfile.ZipFile(p); txt=''
            for n in sorted(n for n in z.namelist() if re.match(r'Contents/section\d+\.xml$',n)):
                s=z.read(n).decode('utf-8','replace')
                txt+='\n'.join(re.sub(r'<[^>]+>','',m) for m in re.findall(r'<hp:t\b[^>]*>(.*?)</hp:t>',s,re.S))+'\n'
    except Exception as e:
        txt='__ERROR__ '+repr(e)
    open(out+'.tmp','w').write(txt); os.replace(out+'.tmp',out)
todo=sorted([x for x in inv if not os.path.exists(REF+x['sha256'][:12]+'.txt')],key=lambda x:x['bytes'])
print('todo',len(todo),flush=True)
with ThreadPoolExecutor(4) as ex: list(ex.map(work,todo))
print('done',len(os.listdir(REF)),'of',len(inv))
os._exit(0)
