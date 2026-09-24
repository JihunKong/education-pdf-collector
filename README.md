# Education PDF collector

공식 교육 문서 수집을 위한 **공개 코드 저장소**입니다. PDF 원본을 공개 배포하는 저장소가 아닙니다.

## 검증된 결과 — 2026-09-24

[교육부 회수 실행](https://github.com/JihunKong/education-pdf-collector/actions/runs/35977100576)은 성공했습니다.
교육부 공식 게시물 105372의 첨부 PDF 3개를 실제로 받아 암호화하고, 수신 환경에서 복호화 및 검증했습니다.

| 문서 | PDF 페이지 | 바이트 | SHA-256 |
|---|---:|---:|---|
| 2026 학교생활기록부 기재요령(초등학교) | 161 | 4906572 | 72dd61629c0f841bbc75adbf9250130a71d44cf2fff2a8568bd6eb905ff2b496 |
| 2026 학교생활기록부 기재요령(중학교) | 173 | 4405661 | 186cfd0355ae64e766640a4df3f7bd94179dc824203edab4c97ef499eaf47578 |
| 2026 학교생활기록부 기재요령(고등학교) | 223 | 4926475 | c122b02eb6d230976c42474cc5dd96937c084dffd2ea29ce597bbb71d5a974cd |

총 557쪽. 바이트 수와 해시, PDF 파싱, 전체 페이지 저해상도 렌더링, 표지를 확인했습니다.
전체 본문 검수, 최신 개정 여부 조사, 수강생 재배포 허락까지 완료했다는 뜻은 아닙니다.

원게시물: https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=316&boardSeq=105372&lev=0&m=0302&opType=N&page=1&s=moe&searchType=null&statusYN=W
원게시물 이용조건: 공공누리 출처표시·상업적 이용금지·변경금지. 배포 목적별 별도 확인이 필요합니다.

## 남은 장애와 현재 배치

인천의 기존 직접 PDF 주소는 PDF가 아니라 다른 페이지로 이동하는 **77바이트 HTML**을 반환했습니다. 그 응답을 PDF로 저장하지 않고 교육부 원게시물의 실제 첨부 경로를 이용했습니다.

[전남 후속 배치](https://github.com/JihunKong/education-pdf-collector/actions/runs/35977574220)에서는 2025 고교학점제 안내서 게시물과 2026 교육공무원 인사실무 후보 PDF가 각각 타임아웃으로 실패했습니다. 삭제·권한차단·문서 부존재로 단정하지 않습니다.
현재 `scripts/recover_official.py`는 이 두 전남 주소를 한 번씩 검사합니다. 교육부 성공 사례의 코드는 커밋 `1209905330723b787334e825a99ef0fc4d9b0340`에 보존되어 있습니다. 원래 요청 160개의 전체 수집은 미완료입니다.

## 공개 저장소에서 결과 보호

- PDF·HWP·원문 HTML·개인 Drive 자료·개인키는 git에 올리지 않습니다.
- 실행 결과 ZIP은 OpenSSL CMS AES-256-GCM / RSA-OAEP-SHA256으로 암호화한 뒤 암호문만 Actions artifact로 3일 보관합니다.
- **현재 워크플로의 수신 인증서는 `keys/transport_session_cert.pem`입니다.** `keys/recipient_cert.pem`은 이전 시험용 공개 인증서로, 현재 결과의 복호화 기준이 아닙니다.
- 대응하는 개인키는 저장소나 Actions에 제공하지 않으며 수신자가 개인적으로 보관합니다. 암호화가 실패하면 원문을 대신 업로드하지 않습니다.
- 인증서 검증을 해제하거나 CAPTCHA·로그인 제한을 우회하지 않습니다. 토큰과 브라우저 쿠키도 수집하지 않습니다.

## 실행과 결과 회수

Ubuntu 24.04에서 최대 5분으로 제한합니다. 예약 실행은 없습니다. 지정된 코드 경로를 main에 변경하거나 Actions의 Run workflow로 실행합니다. 외부 pull request에서는 수집하지 않습니다.

```bash
python3 -m unittest discover -s scripts -p 'test_public_pdf_probe.py' -v
python3 scripts/recover_official.py
python3 -c "from pathlib import Path; from scripts.seal_results import seal; seal(Path('output'), Path('keys/transport_session_cert.pem'), Path('sealed/results.cms'))"
```

수신자는 별도로 전달된 개인키 백업과 OpenSSL 3으로 복호화합니다.

```bash
openssl cms -decrypt -binary -inform DER \
  -in results.cms -recip public_cert.pem \
  -inkey private.pem -out recovered.zip
```

개인키와 복호화한 원본 ZIP은 공개 저장소, 이슈, 공개 게시판에 올리지 마세요.
