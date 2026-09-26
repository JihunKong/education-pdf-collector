import json,re,os,subprocess,hashlib,html,time,datetime,sys
UA='education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'
OUT=os.path.expanduser('~/epc_out'); ST=OUT+'/state.json'
sel=json.load(open(sys.argv[1])); region=sys.argv[2]; prefix=sys.argv[3]
s=json.load(open(ST)); rec=s['records']
known={v['sha256']:v.get('saved_path') for v in rec.values() if v.get('sha256') and v.get('saved_path')}
norm=lambda t: re.sub(r'[\s?·ㆍ_]','',re.sub(r'\.(pdf|hwpx?)$','',t,flags=re.I))
T0=time.time(); os.makedirs(f'{OUT}/pdfs/{region}',exist_ok=True)
def sig_ok(b,ext): return b[:4]==b'%PDF' if ext=='pdf' else (b[:2]==b'PK' if ext=='hwpx' else b[:8]==b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
for it in sel:
    purl=it['url']
    if rec.get(purl,{}).get('status')=='page_scanned': continue
    if time.time()-T0>140: break
    t=subprocess.run(['curl','-sS','-m','40','-A',UA,purl],capture_output=True).stdout.decode('utf-8','replace')
    atts=[]
    for m in re.finditer(r"previewAjax\('([^']+)','([^']+)'\)",t):
        a=(html.unescape(m.group(1)),html.unescape(m.group(2)).strip())
        if a not in atts: atts.append(a)
    if not atts:
        for m in re.finditer(r"goFileDown\('([0-9a-f]+)'\);\"[^>]*title=\"([^\"]+?) 다운로드\"",t):
            atts.append(('/goe/na/ntt/comm/nttFileDownload.do?fileKey='+m.group(1),html.unescape(m.group(2)).strip()))
    if it['mode']=='file':
        want=norm(it['title'].rstrip('.'))
        atts=[a for a in atts if norm(a[1]).startswith(want[:max(8,len(want)-3)]) or want.startswith(norm(a[1])[:20])] or atts[:0]
    atts=[a for a in atts if re.search(r'\.(pdf|hwpx?)$',a[1],re.I)]
    seq=re.search(r'nttSn=(\d+)',purl).group(1)
    n=0
    for i,(href,name) in enumerate(atts,1):
        fu=href if href.startswith('http') else 'https://www.goe.go.kr'+href
        if rec.get(fu,{}).get('status') in ('downloaded','duplicate_bytes'): continue
        tmp='/tmp/goe_dl.bin'
        subprocess.run(['curl','-sS','-L','-m','170','-A',UA,'-o',tmp,fu])
        b=open(tmp,'rb').read(); ext=name.rsplit('.',1)[1].lower(); h=hashlib.sha256(b).hexdigest()
        r=dict(id=f'{prefix}-{seq}-{i}',kind=ext,title=name,region=region,url=fu,parent_url=purl,checked_at=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),bytes=len(b),sha256=h,declared_bytes_match=None,note='경기도교육청 통합검색으로 찾은 게시물 첨부')
        if not sig_ok(b,ext): r['status']='bad_signature'
        elif h in known: r['status']='duplicate_bytes'; r['duplicate_of']=known[h]
        else:
            safe=re.sub(r'[\\/:*?"<>|]',' ',name)[:90]
            sp=f'pdfs/{region}/{prefix}-{seq}-{i}_{safe}__{h[:10]}.{ext}'
            open(f'{OUT}/{sp}','wb').write(b); r['status']='downloaded'; r['saved_path']=sp; known[h]=sp; n+=1
        rec[fu]=r; print(r['id'],r['status'],len(b),name[:60],flush=True)
    rec[purl]=dict(id=f'{prefix}-{seq}',kind='page',title=it['pattern'],region=region,url=purl,status='page_scanned' if atts else 'no_pdf_link',checked_at=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
    json.dump(s,open(ST,'w'),ensure_ascii=False,indent=1)
json.dump(s,open(ST,'w'),ensure_ascii=False,indent=1)
print('pages done',sum(1 for it in sel if it['url'] in rec),'of',len(sel))
