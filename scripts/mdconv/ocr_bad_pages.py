import os, glob, json, subprocess, tempfile, sys
sys.path.insert(0,'/root/ocr')
from concurrent.futures import ProcessPoolExecutor
os.environ['TESSDATA_PREFIX']='/root/tessdata'; os.environ['OMP_THREAD_LIMIT']='1'
SRC='/mnt/user-data/uploads/AILEVELUP/교육자료 PDF 수집/collected/pdfs/'
OUT='/root/ocr/cache3/'
from ocr_pages import sha
def job(a):
    p,i,d=a
    import pymupdf
    page=pymupdf.open(p)[i-1]
    pix=page.get_pixmap(dpi=200)
    fd,png=tempfile.mkstemp(suffix='.png'); os.close(fd); pix.save(png)
    try: txt=subprocess.run(['tesseract',png,'-','-l','kor+eng','--psm','4'],capture_output=True,text=True,timeout=300).stdout
    finally: os.unlink(png)
    out=[];blank=0
    for l in txt.splitlines():
        if l.strip(): out.append(l.strip()); blank=0
        else:
            blank+=1
            if blank==1: out.append('')
    open(d+f'p{i:04d}.ocr.md','w').write('\n'.join(out).strip())
if __name__=='__main__':
    bad=json.load(open('/root/ocr/bad.json')); jobs=[]
    for p in glob.glob(SRC+'*/*.pdf'):
        k=p.rsplit('__',1)[-1][:10]
        if k in bad:
            d=OUT+sha(p)[:12]+'/'; os.makedirs(d,exist_ok=True)
            jobs+=[(p,i,d) for i in bad.pop(k)]
    print('jobs',len(jobs),'unmatched',list(bad),flush=True)
    with ProcessPoolExecutor(2) as ex: list(ex.map(job,jobs))
    print('DONE',flush=True)
