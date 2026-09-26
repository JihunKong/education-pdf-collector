import sys, tempfile, unittest, json, subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_batch import Collector, CurlTransport, TransportError, safe_url, pdf_signature, extract_links, filename
PDF=b'%PDF-1.7\nSynthetic fixture, not a real document\n%%EOF\n'
URL='https://www.moe.go.kr/a.pdf'
JOB={'id':'T1','url':URL,'kind':'pdf','title':'fixture','region':'test'}
class Fake:
    def __init__(self,bodies):self.bodies=bodies;self.calls=[]
    def fetch(self,url,dst,max_bytes,referer=''):
        self.calls.append(url);body=self.bodies[url]
        if isinstance(body,Exception):raise body
        if len(body)>max_bytes:raise TransportError('size_limit',{})
        dst.write_bytes(body);return {'final_url':url,'http_code':200}
class Tests(unittest.TestCase):
    def test_https(self):self.assertEqual(safe_url(URL),URL)
    def test_reject_scope(self):
        for u in ('http://www.moe.go.kr/a','https://evil.test/','https://www.moe.go.kr.evil.test/a','https://user:pw@www.moe.go.kr/a','https://127.0.0.1/a','https://www.moe.go.kr:8443/a','https://www.moe.go.kr/logout'):
            self.assertFalse(safe_url(u),u)
    def test_signature(self):
        self.assertTrue(pdf_signature(PDF));self.assertFalse(pdf_signature(b'<html>Blocked</html>'));self.assertFalse(pdf_signature(PDF[:-7]))
    def test_relative_encoding(self):self.assertIn('%EA',safe_url('/한글.pdf','https://www.moe.go.kr/x'))
    def test_filename(self):self.assertNotIn('/',filename('../x/y.pdf'))
    def test_literal_dext(self):
        s="DEXT5UPLOAD.AddUploadedFile('1','교육부.pdf','/upload/document.pdf','3','4', G);"
        self.assertEqual(extract_links(s,URL)[0]['url'],'https://www.moe.go.kr/upload/document.pdf')
    def test_no_inferred_js(self):self.assertEqual(extract_links('<a href="javascript:unknown(123)">a.pdf</a>',URL),[])
    def test_nonpdf_skipped(self):
        s='<li>forms.hwp<a href="/fileDown.do?id=1">다운로드</a></li><li>guide.pdf<a href="/fileDown.do?id=2">다운로드</a></li>'
        self.assertEqual(len(extract_links(s,URL)),1)
    def test_preserve_bytes_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fake({URL:PDF});c=Collector(Path(d),f);self.assertEqual(c.run([JOB]),0)
            self.assertEqual((Path(d)/c.rows[0]['saved_path']).read_bytes(),PDF)
            f2=Fake({});c2=Collector(Path(d),f2);self.assertEqual(c2.run([JOB]),0);self.assertEqual(f2.calls,[])
    def test_corrupt_cache_refetched(self):
        with tempfile.TemporaryDirectory() as d:
            c=Collector(Path(d),Fake({URL:PDF}));c.run([JOB]);(Path(d)/c.rows[0]['saved_path']).write_bytes(b'bad')
            f=Fake({URL:PDF});Collector(Path(d),f).run([JOB]);self.assertEqual(len(f.calls),1)
    def test_deduplicate(self):
        with tempfile.TemporaryDirectory() as d:
            u2=URL+'?mirror=1';c=Collector(Path(d),Fake({URL:PDF,u2:PDF}));c.run([JOB,dict(JOB,id='T2',url=u2)])
            self.assertEqual(c.rows[1]['status'],'duplicate_bytes');self.assertEqual(len(list(Path(d).rglob('*.pdf'))),1)
    def test_partial_is_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            u2=URL+'?failure=1';c=Collector(Path(d),Fake({URL:PDF,u2:TransportError('tcp_connect_failure',{})}))
            self.assertEqual(c.run([JOB,dict(JOB,id='T2',url=u2)]),2)
            self.assertEqual(json.loads((Path(d)/'run_summary.json').read_text())['status'],'partial')
    def test_html_is_not_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            c=Collector(Path(d),Fake({URL:b'<html>Error</html>'}));self.assertEqual(c.run([JOB]),2);self.assertEqual(len(list(Path(d).rglob('*.pdf'))),0)
    def test_page_discovers_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            p='https://www.moe.go.kr/page';c=Collector(Path(d),Fake({p:b'<a href="/a.pdf">test.pdf</a>',URL:PDF}))
            self.assertEqual(c.run([dict(JOB,url=p,kind='page')]),0);self.assertEqual(len(list(Path(d).rglob('*.pdf'))),1)
    def test_budget_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            c=Collector(Path(d),Fake({URL:PDF}));self.assertEqual(c.run([JOB,dict(JOB,id='T2',url=URL+'?b')],max_items=1),2)
            self.assertEqual(len(json.loads((Path(d)/'state.json').read_text())['pending']),1)
    def test_circuit_breaker(self):
        with tempfile.TemporaryDirectory() as d:
            response=subprocess.CompletedProcess([],28,json.dumps({'http_code':0,'time_connect':0,'time_namelookup':.1}),'Timeout')
            t=CurlTransport(delay=0)
            with patch('collect_batch.subprocess.run',return_value=response) as run:
                with self.assertRaises(TransportError) as first:t.fetch(URL,Path(d)/'tmp',100)
                self.assertEqual(first.exception.stage,'tcp_connect_failure')
                with self.assertRaises(TransportError) as second:t.fetch(URL+'?2',Path(d)/'tmp',100)
                self.assertEqual(second.exception.stage,'host_deferred');self.assertEqual(run.call_count,1)
    def test_jeonnam_file_attach(self):
        page='https://www.jge.go.kr/open/na/ntt/selectNttInfo.do?mi=551&nttSn=5135663'
        s=('<a href="'+page.replace('&','&amp;')+'">미리보기 (전남)고교학점제+운영+안내서.pdf</a>'
           '<script>wFileUpload.fileAttachAddTxt("(전남)고교학점제+운영+안내서.pdf","/upload/open/na/bbs_297/ntt_5135663/doc_x.pdf","10281996");</script>')
        links=extract_links(s,page)
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]['url'],'https://www.jge.go.kr/upload/open/na/bbs_297/ntt_5135663/doc_x.pdf')
        self.assertEqual(links[0]['label'],'(전남)고교학점제 운영 안내서.pdf')
        self.assertEqual(links[0]['declared_bytes'],10281996)
    def test_declared_bytes_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            p='https://www.jge.go.kr/page';u='https://www.jge.go.kr/upload/a.pdf'
            body=('<script>x.fileAttachAddTxt("a.pdf","/upload/a.pdf","%d");</script>'%len(PDF)).encode()
            c=Collector(Path(d),Fake({p:body,u:PDF}));self.assertEqual(c.run([dict(JOB,url=p,kind='page')]),0)
            self.assertTrue(c.rows[1]['declared_bytes_match'])
            # Resume from the same output folder: cached PDF keeps the size check.
            f2=Fake({p:body});c2=Collector(Path(d),f2);self.assertEqual(c2.run([dict(JOB,url=p,kind='page')]),0)
            self.assertEqual(c2.rows[1]['status'],'existing_verified');self.assertTrue(c2.rows[1]['declared_bytes_match'])
            self.assertEqual(f2.calls,[p])
if __name__=='__main__':unittest.main()
