# -*- coding: utf-8 -*-
"""Tick the self-check boxes of one week in the school plan .docx and write the 修正 note.

    python scripts/fill_plan_check.py 9 "修正說明文字"            # ☑完成 + ☑修正：文字
    python scripts/fill_plan_check.py 9 "" --partial               # ☑部分完成 only

The plan file lives outside the repo (it carries the student's name). A timestamped backup is written to
CACHE_DIR/plan_backups before every change. Close the file in Word first.
"""
import re
import sys
import shutil
import zipfile
import datetime as dt
import pathlib
import xml.dom.minidom

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C   # noqa: E402

PLAN = pathlib.Path.home() / "OneDrive" / "文件" / "許博渭_高二自主學習計畫書.docx"
T = r"<w:t[^>]*>([^<]*)</w:t>"


def text(p):
    return "".join(re.findall(T, p))


def set_runs(p, new_texts):
    """Replace the texts of the paragraph's runs in order; extra runs are emptied."""
    it = iter(new_texts)
    return re.sub(T, lambda m: f'<w:t xml:space="preserve">{next(it, "")}</w:t>', p)


def main(week: int, note: str, partial=False):
    z = zipfile.ZipFile(PLAN)
    xml_ = z.read("word/document.xml").decode("utf-8")
    paras = list(re.finditer(r"<w:p[ >].*?</w:p>", xml_, flags=re.S))
    texts = [text(m.group(0)) for m in paras]
    start = texts.index(f"第{week}週")
    end = texts.index(f"第{week + 1}週") if f"第{week + 1}週" in texts else len(texts)
    edits = {}
    for i in range(start, end):
        t = texts[i].strip()
        if t in ("□完成", "☑完成"):
            edits[i] = ["□" if partial else "☑", "完成"]
        elif t in ("□部分完成", "☑部分完成"):
            edits[i] = ["☑" if partial else "□", "部分完成"]
        elif t.startswith(("□修正", "☑修正")):
            edits[i] = ["☑", f"修正：{note}"] if note else ["□", "修正"]
    if len(edits) != 3:
        sys.exit(f"找不到第 {week} 週的三個勾選欄（找到 {len(edits)} 個）")
    out = xml_
    for i in sorted(edits, reverse=True):
        m = paras[i]
        out = out[:m.start()] + set_runs(m.group(0), edits[i]) + out[m.end():]
    xml.dom.minidom.parseString(out.encode("utf-8"))
    bdir = C.CACHE_DIR / "plan_backups"; bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLAN, bdir / f"plan_{dt.datetime.now():%Y%m%d_%H%M%S}.docx")
    tmp = PLAN.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in z.infolist():
            if not it.is_dir():
                zo.writestr(it.filename, out.encode("utf-8") if it.filename == "word/document.xml" else z.read(it.filename))
    z.close()
    try:
        tmp.replace(PLAN)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        sys.exit("計畫書正在 Word 中開啟，請先關閉再執行")
    chk = zipfile.ZipFile(PLAN).read("word/document.xml").decode("utf-8")
    ps = [text(p) for p in re.findall(r"<w:p[ >].*?</w:p>", chk, flags=re.S)]
    i = ps.index(f"第{week}週")
    print([t for t in ps[i:i + 16] if "完成" in t[:5] or "修正" in t[:3]])


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "", "--partial" in sys.argv)
