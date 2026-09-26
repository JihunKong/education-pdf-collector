import os, sys, glob, hashlib, subprocess, tempfile
from concurrent.futures import ProcessPoolExecutor
os.environ['TESSDATA_PREFIX']='/root/tessdata'; os.environ['OMP_THREAD_LIMIT']='1'; os.environ['OMP_NUM_THREADS']='1'
SRC='/mnt/user-data/uploads/AILEVELUP/교육자료 PDF 수집/collected/pdfs/'
OUT='/root/ocr/cache2/'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def put(dest,txt):
    tmp=dest+'.tmp'; open(tmp,'w').write(txt); os.replace(tmp,dest)
def job(a):
    p,i,d=a
    import pymupdf
    doc=pymupdf.open(p); page=doc[i]
    raw=page.get_text().strip()
    if len(raw)>=30:
        import pymupdf4llm
        md=pymupdf4llm.to_markdown(doc,pages=[i],use_ocr=False,header=False,footer=False,show_progress=False)
        put(d+f'p{i+1:04d}.md',md.strip()); return
    pix=page.get_pixmap(dpi=200)
    fd,png=tempfile.mkstemp(suffix='.png'); os.close(fd); pix.save(png)
    try:
        txt=subprocess.run(['tesseract',png,'-','-l','kor+eng','--psm','4'],capture_output=True,text=True,timeout=300).stdout
    finally: os.unlink(png)
    out=[];blank=0
    for l in txt.splitlines():
        if l.strip(): out.append(l.strip()); blank=0
        else:
            blank+=1
            if blank==1: out.append('')
    put(d+f'p{i+1:04d}.ocr.md','\n'.join(out).strip())
if __name__=='__main__':
    import pymupdf
    EXC=('T072-cand','T001-pdf','school-repost')
    jobs=[]
    for p in sorted(glob.glob(SRC+'*/*.pdf')):
        if any(e in p for e in EXC): continue
        d=OUT+sha(p)[:12]+'/'; os.makedirs(d,exist_ok=True)
        for i in range(pymupdf.open(p).page_count):
            if not (os.path.exists(d+f'p{i+1:04d}.md') or os.path.exists(d+f'p{i+1:04d}.ocr.md')): jobs.append((p,i,d))
    print('jobs',len(jobs),flush=True)
    with ProcessPoolExecutor(2) as ex:
        for k,_ in enumerate(ex.map(job,jobs,chunksize=1)):
            if k%50==0: print(k,flush=True)
    print('DONE',flush=True)
