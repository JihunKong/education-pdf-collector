"""새로 만든 Markdown 트리를 사용자 폴더에 반영한다.

바뀐 파일만 복사하고, 새 트리에 없는 파일은 지우지 않고 보관 폴더로 옮긴다(연결 폴더에서는 삭제가 막혀 있을 수 있다).

사용법: python3 sync_tree.py 새트리 대상폴더 보관폴더
"""
import filecmp
import os
import shutil
import sys

src, dst, trash = sys.argv[1:4]
copied = moved = 0
for dp, _, fs in os.walk(src):
    for f in fs:
        s = os.path.join(dp, f)
        d = os.path.join(dst, os.path.relpath(s, src))
        if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            copied += 1
for dp, _, fs in os.walk(dst):
    for f in fs:
        d = os.path.join(dp, f)
        rel = os.path.relpath(d, dst)
        if not os.path.exists(os.path.join(src, rel)):
            t = os.path.join(trash, rel)
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.move(d, t)
            moved += 1
# 빈 폴더 정리는 삭제 권한이 필요하므로 하지 않는다
print('복사', copied, '보관 폴더로 이동', moved)
