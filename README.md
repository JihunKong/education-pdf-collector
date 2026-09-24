# Education PDF collector

공식 교육 문서 수집을 위한 공개 코드 저장소입니다. PDF 공개 배포 저장소가 아닙니다.

## 현재 단계

공개 PDF 1개(인천교육청에 게시된 2026 초등학교 생활기록부 기재요령)와
전남교육청의 2025 고교학점제 운영 안내서 게시물 HTML을 받는 제한된 연결 시험입니다.
이 시험만으로 요청 문서 160개 수집 완료 또는 최신 판본 확인을 의미하지 않습니다.

- GitHub Actions / Ubuntu 24.04 / 최대 5분. 예약 실행은 없습니다.
- 허용된 공식 HTTPS 호스트만 요청하며 인증서 검증을 해제하지 않습니다.
- API 키, 브라우저 쿠키, 개인 Drive 자료를 사용하지 않습니다.
- 파일 크기와 PDF 서명 검사는 수행하지만 판본·본문·이용조건은 별도 확인해야 합니다.

## 공개 저장소에서 결과 보호

PDF와 원문 HTML은 git에 커밋하지 않습니다. 결과 ZIP을 OpenSSL CMS AES-256-GCM,
RSA-OAEP-SHA256으로 암호화한 뒤 암호문만 Actions artifact로 3일 보관합니다.
로그에는 파일 내용이 아닌 성공 여부, 오류 유형, 바이트 수만 기록합니다.
`keys/recipient_cert.pem`은 공개 인증서입니다. 대응하는 개인키는 이 저장소나
GitHub Actions에 올리지 않으며, 수신자가 별도 보관해야 합니다.

공개 저장소의 artifact도 타인이 내려받을 수 있으므로 암호화를 생략하면 안 됩니다.
암호화 실패 시 원본을 대신 업로드하지 않습니다. 암호화는 문서 이용허락을 대체하지 않습니다.

## 실행

기본 브랜치의 시험 코드 변경 시 또는 Actions의 Run workflow로 실행합니다.
외부 pull request에서 원문을 수집하거나 자동 병합하지 않습니다.

```bash
python3 -m unittest discover -s scripts -p 'test_public_pdf_probe.py' -v
python3 scripts/public_pdf_probe.py
python3 scripts/seal_results.py
```

복호화(OpenSSL 3 지원 환경에서 수신자가 실행):

```bash
openssl cms -decrypt -binary -inform DER \
  -in results.cms -recip keys/recipient_cert.pem \
  -inkey /secure/path/recipient_private_key.pem -out recovered.zip
```

개인키와 복호화된 결과는 공개 저장소에 올리지 마세요. 수강생 배포 전에는
출처, 적용 지역·연도, 개정판, 문서별 이용조건을 따로 검토해야 합니다.
