#!/usr/bin/env python3
"""Public PDF collection with durable checkpoints and truthful partial results.
Python 3.9+ and curl. HTTPS only; no browser cookies or authentication bypass.
A transport check is NOT a bibliographic, legal or full-PDF validation.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, subprocess, tempfile, time
from collections import Counter, deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, quote

APPROVED = {'moe.go.kr','jne.go.kr','jne.kr','jge.go.kr','gen.go.kr','cbe.go.kr',
            'goe.go.kr','pen.go.kr','sen.go.kr','dge.go.kr','ice.go.kr','dje.go.kr',
            'use.go.kr','sje.go.kr','gwe.go.kr','cne.go.kr','jbe.go.kr','jbedu.kr',
            'gbe.kr','gne.go.kr','jje.go.kr','jnei.go.kr'}
DOWNLOAD = re.compile(r'\.pdf(?:$|[?#])|filedown|download|downfile|downpost', re.I)
NONPDF = re.compile(r'\.(?:hwp|hwpx|zip|exe|msi|dmg|docx?|xlsx?|pptx?)(?:\b|$)',re.I)
# Some school boards reject curl's default agent with 400 RequestBlocked.
# Identify the tool honestly instead of impersonating a browser.
USER_AGENT = 'education-pdf-collector/1.1 (+https://github.com/JihunKong/education-pdf-collector)'
UNSAFE = re.compile(r'login|logout|signin|signout|delete|remove|insert|update|register|write\.do',re.I)

def safe_url(url: str, base: str='') -> str:
    p=urlsplit(urljoin(base,html.unescape(url)))
    try: valid_port = p.port in (None,443)
    except ValueError: return ''
    if p.scheme!='https' or not p.hostname or p.username or p.password or not valid_port: return ''
    if not any(p.hostname==x or p.hostname.endswith('.'+x) for x in APPROVED): return ''
    if UNSAFE.search(p.path+'?'+p.query): return ''
    return urlunsplit(('https',p.netloc,quote(p.path,safe="/%:@+;,=-_~.!$&'()*"),quote(p.query,safe="/%?@+;,=:-_~.!$&'()*[]"),''))

def pdf_signature(data: bytes) -> bool:
    return len(data)>20 and data[:1024].lstrip().startswith(b'%PDF-') and b'%%EOF' in data[-8192:]

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def save_json(path: Path, data) -> None:
    tmp=path.with_suffix(path.suffix+'.part')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

def filename(text: str) -> str:
    text=re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_',text).strip(' .')
    text=text.encode('utf-8')[:140].decode('utf-8','ignore') or 'document'
    return text

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.links=[]; self.a=None; self.context=''
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag in ('li','dd'): self.context=''
        if tag=='a': self.a=[d.get('href',''), d.get('title','')+' '+self.context, d.get('onclick','')]
        if tag=='img' and self.a: self.a[1]+=' '+d.get('alt','')
    def handle_data(self,data):
        self.context=(self.context+' '+data)[-350:]
        if self.a:self.a[1]+=' '+data
    def handle_endtag(self,tag):
        if tag=='a' and self.a:self.links.append(tuple(self.a));self.a=None

def extract_links(text: str, base: str) -> list:
    """Only literal href/DEXT upload paths; do not execute or guess JavaScript."""
    parser=LinkParser(); parser.feed(text); result={}; declared={}
    page=safe_url(base)
    for href,label,js in parser.links:
        if NONPDF.search(label): continue
        url=safe_url(href,base)
        # A preview/self link (href="#" or the post itself) is not an attachment.
        if not url or url==page: continue
        if DOWNLOAD.search(url) or '.pdf' in label.lower():result[url]=label.strip()
    # These paths occur verbatim in the official page's upload initialization.
    for match in re.finditer(r"AddUploadedFile\(\s*'[^']*'\s*,\s*'([^']+\.pdf)'\s*,\s*'([^']+\.pdf)'",text,re.I):
        url=safe_url(match[2],base)
        if url:result[url]=match[1]
    # Jeonnam (jne/jge.go.kr) boards: wFileUpload.fileAttachAddTxt("name.pdf","/upload/...pdf","bytes")
    for match in re.finditer(r"""fileAttachAddTxt\(\s*["']([^"']+\.pdf)["']\s*,\s*["']([^"']+\.pdf)["']\s*(?:,\s*["'](\d+)["'])?""",text,re.I):
        url=safe_url(match[2],base)
        if url:
            result[url]=html.unescape(match[1]).replace('+',' ')
            if match[3]:declared[url]=int(match[3])
    return [dict({'url':u,'label':label},**({'declared_bytes':declared[u]} if u in declared else {}))
            for u,label in result.items()]

class TransportError(Exception):
    def __init__(self,stage,details):super().__init__(stage);self.stage=stage;self.details=details

class CurlTransport:
    def __init__(self,delay=1.5):self.delay=delay;self.last={};self.blocked={}
    def fetch(self,url: str,dst: Path,max_bytes: int,referer: str='') -> dict:
        chain=[]
        for _ in range(5):
            url=safe_url(url)
            if not url:raise TransportError('unsafe_url',{})
            host=urlsplit(url).hostname
            if host in self.blocked:raise TransportError('host_deferred',{'cause':self.blocked[host]})
            time.sleep(max(0,self.delay-(time.monotonic()-self.last.get(host,0))))
            self.last[host]=time.monotonic()
            args=['curl','--proto','=https','--silent','--show-error','--connect-timeout','10',
                  '--max-time','90','--max-filesize',str(max_bytes),'--output',str(dst),
                  '--write-out','%{json}','--header','Accept-Encoding: identity','--user-agent',USER_AGENT]
            if referer and safe_url(referer):args+=['--referer',referer]
            try:r=subprocess.run(args+[url],capture_output=True,text=True,timeout=95)
            except subprocess.TimeoutExpired as e:
                raise TransportError('process_timeout',{}) from e
            try:meta=json.loads(r.stdout)
            except ValueError:meta={}
            info={k:meta.get(k) for k in ['http_code','content_type','size_download','time_namelookup',
                    'time_connect','time_appconnect','time_starttransfer','time_total','redirect_url']}
            info.update(final_url=url,curl_exit=r.returncode,redirect_chain=chain)
            code=int(info.get('http_code') or 0)
            if r.returncode:
                stage='transfer_error'
                if r.returncode==6:stage='dns_failure'
                elif r.returncode in (7,28) and not info.get('time_connect'):stage='tcp_connect_failure'
                elif r.returncode in (35,51,60):stage='tls_failure'
                elif r.returncode==28:stage='read_timeout'
                elif r.returncode==63:stage='size_limit'
                if stage in ('dns_failure','tcp_connect_failure'):self.blocked[host]=stage
                raise TransportError(stage,info)
            if code in (301,302,303,307,308):
                dest=meta.get('redirect_url') or ''
                if not safe_url(dest):raise TransportError('unsafe_redirect',info)
                chain.append({'from':url,'to':dest});url=dest;continue
            if code!=200:
                if code in (401,403,429):self.blocked[host]='http_'+str(code)
                raise TransportError('http_'+str(code),info)
            if not dst.exists() or dst.stat().st_size>max_bytes:raise TransportError('size_limit',info)
            return info
        raise TransportError('redirect_limit',{'redirect_chain':chain})

class Collector:
    def __init__(self,out: Path,transport=None):
        self.out=out.resolve();self.out.mkdir(parents=True,exist_ok=True)
        self.transport=transport or CurlTransport();self.file=self.out/'state.json'
        self.state=json.loads(self.file.read_text(encoding='utf-8')) if self.file.exists() else {'records':{},'pending':[]}
        self.rows=[]; self.seen_hashes={}
        for r in self.state['records'].values():
            if self.cached(r):self.seen_hashes[r['sha256']]=r['saved_path']
    def cached(self,row):
        try:
            p=(self.out/row['saved_path']).resolve()
            return self.out in p.parents and p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
        except (KeyError,OSError):return False
    def run(self,jobs: list,max_items=40,max_total_mb=250):
        queue=deque(jobs);seen=set();total=0
        while queue and len(self.rows)<max_items:
            job=queue.popleft();url=job['url'];kind=job.get('kind','pdf')
            if url in seen:continue
            seen.add(url);row=dict(job,checked_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),status='pending')
            old=self.state['records'].get(url,{})
            if kind=='pdf' and self.cached(old):
                row.update(status='existing_verified',saved_path=old['saved_path'],sha256=old['sha256'],bytes=old['bytes'])
                if 'declared_bytes' in job:row['declared_bytes_match']=(old['bytes']==job['declared_bytes'])
            else:
                tmp=self.out/'transfer.part'
                remaining=int(max_total_mb*1024*1024-total)
                limit=min(75*1024*1024 if kind=='pdf' else 4*1024*1024,remaining)
                try:
                    if limit<=0:raise TransportError('batch_size_limit',{})
                    meta=self.transport.fetch(url,tmp,limit,job.get('parent_url',''))
                    row['transport']=meta;data=tmp.read_bytes()
                    if kind=='page' and not pdf_signature(data):
                        text=data.decode('utf-8','replace');links=extract_links(text,meta['final_url'])
                        cap=job.get('max_attachments',12);links=links[:cap]
                        pattern=job.get('attachment_filter')
                        if pattern:links=[x for x in links if re.search(pattern,x['label']+' '+x['url'],re.I)]
                        row.update(status='page_scanned' if links else 'no_pdf_link',attachments=links)
                        for i,link in enumerate(links,1):
                            child=dict(job,id=job['id']+f'-{i}',url=link['url'],kind='pdf',
                                       title=link['label'] or job['title'],parent_url=meta['final_url'])
                            if 'declared_bytes' in link:child['declared_bytes']=link['declared_bytes']
                            queue.appendleft(child)
                    else:
                        if not pdf_signature(data):raise TransportError('not_a_complete_pdf',meta)
                        h=hashlib.sha256(data).hexdigest();row.update(sha256=h,bytes=len(data),
                            bibliographic_match='needs_review',redistribution='not_reviewed')
                        if 'declared_bytes' in job:row['declared_bytes_match']=(len(data)==job['declared_bytes'])
                        if h in self.seen_hashes:row.update(status='duplicate_bytes',saved_path=self.seen_hashes[h])
                        else:
                            rel=Path('pdfs')/filename(job.get('region','unclassified'))/(filename(job['id']+'_'+job['title'])+'__'+h[:10]+'.pdf')
                            dst=self.out/rel;dst.parent.mkdir(parents=True,exist_ok=True);tmp.replace(dst)
                            row.update(status='downloaded',saved_path=rel.as_posix());self.seen_hashes[h]=rel.as_posix();total+=len(data)
                except TransportError as e:row.update(status=e.stage,error=e.details)
                except Exception as e:row.update(status='unexpected_error',error=type(e).__name__+': '+str(e)[:300])
                finally:tmp.unlink(missing_ok=True)
            self.rows.append(row);self.state['records'][url]=row;self.state['pending']=list(queue);save_json(self.file,self.state)
            print(json.dumps({'id':row['id'],'status':row['status'],'bytes':row.get('bytes')},ensure_ascii=False),flush=True)
        success={'downloaded','existing_verified','duplicate_bytes','page_scanned'}
        failures=[r for r in self.rows if r['status'] not in success]
        report={'status':'complete_selected_batch' if not failures and not queue else 'partial',
                'new_pdfs':sum(r['status']=='downloaded' for r in self.rows),
                'status_counts':dict(Counter(r['status'] for r in self.rows)),
                'failed_items':len(failures),'pending_items':len(queue),
                'scope':'Selected public sources only, not all requested documents.',
                'verification':'Header/EOF transport check only; full PDF and edition validation required.'}
        save_json(self.out/'run_summary.json',report);save_json(self.out/'run_records.json',self.rows)
        save_json(self.out/'retry_queue.json',failures+list(queue))
        return 0 if report['status']=='complete_selected_batch' else 2

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('output'))
    p.add_argument('--max-items',type=int,default=40);p.add_argument('--max-total-mb',type=int,default=250)
    a=p.parse_args()
    if not 1<=a.max_items<=500 or not 1<=a.max_total_mb<=1024:p.error('Invalid collection budget')
    jobs=json.loads(a.manifest.read_text(encoding='utf-8'))
    if not isinstance(jobs,list) or not jobs:p.error('Manifest must contain at least one public source')
    for j in jobs:
        if not all(k in j for k in ('id','url','title')) or not safe_url(j['url']):p.error('Invalid manifest source')
    a.output.mkdir(parents=True,exist_ok=True);lock=a.output/'.collector.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:p.error('Another collector may be active. Do not run two copies against the same output folder.')
    os.close(fd)
    try:return Collector(a.output).run(jobs,a.max_items,a.max_total_mb)
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':raise SystemExit(main())
