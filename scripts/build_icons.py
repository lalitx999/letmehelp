"""สร้าง sprite ไอคอนขนาดเล็กจาก Bootstrap Icons (MIT) เฉพาะไอคอนที่ใช้จริง
ใช้: python scripts/build_icons.py /path/to/bootstrap-icons/bootstrap-icons.svg
แก้รายการ ICONS ด้านล่างเมื่อต้องใช้ไอคอนเพิ่ม แล้วรันใหม่"""
import re
import sys
from pathlib import Path

ICONS = """
house house-door play-circle play-circle-fill play-fill pause-fill journal-text journal-bookmark journal-richtext
calendar3 calendar-check calendar-event person person-circle person-plus person-check person-badge people
box-arrow-in-right box-arrow-right box-arrow-up-right receipt receipt-cutoff qr-code qr-code-scan cloud-arrow-up upload
file-earmark-pdf file-earmark-text file-earmark-arrow-down check check2 check-circle check-circle-fill x-lg x-circle x-circle-fill
hourglass-split arrow-right arrow-left arrow-up-right arrow-repeat chevron-left chevron-right chevron-down chevron-up
speedometer2 collection-play collection credit-card-2-front bar-chart-line graph-up graph-up-arrow download
clock clock-history lightning-charge trophy mortarboard mortarboard-fill bookmark-check telephone envelope lock lock-fill
eye eye-slash pencil-square trash3 plus-lg dash camera-video shield-check patch-check list-check fire book book-half
search circle info-circle exclamation-triangle exclamation-circle gear bell tags folder2-open headset key bullseye
rocket-takeoff lightbulb infinity laptop phone tablet wallet2 cash-stack image grid-1x2 list layout-sidebar
chat-dots translate spellcheck megaphone layers stars globe2 sliders filter-left skip-forward-fill skip-backward-fill
hand-thumbs-up pc-display-horizontal window-stack file-earmark-spreadsheet file-earmark-bar-graph cursor
patch-question question-circle youtube line facebook instagram tiktok telegram box-arrow-up plus-square cookie shield-check file-earmark-lock2 arrow-down-short arrow-up-short dot
three-dots three-dots-vertical files star star-fill toggle-on toggle-off arrow-counterclockwise person-x person-dash shield-lock inbox folder-plus journal-check check2-all clipboard-check box-seam trash arrow-up arrow-down envelope-check person-gear gear-fill funnel clock-history wallet
""".split()


def main(src: str) -> None:
    text = Path(src).read_text()
    symbols = dict(re.findall(r'<symbol class="[^"]*" viewBox="([^"]*)" id="([^"]*)">(.*?)</symbol>', text, re.S) and
                   [(m[1], (m[0], m[2])) for m in re.findall(r'<symbol class="[^"]*" viewBox="([^"]*)" id="([^"]*)">(.*?)</symbol>', text, re.S)])
    out, missing = [], []
    for name in ICONS:
        if name in symbols:
            vb, body = symbols[name]
            out.append(f'<symbol id="{name}" viewBox="{vb}">{body}</symbol>')
        else:
            missing.append(name)
    svg = '<svg xmlns="http://www.w3.org/2000/svg">' + "".join(out) + "</svg>"
    dest = Path(__file__).resolve().parent.parent / "static/vendor/bootstrap-icons/icons.svg"
    dest.write_text(svg)
    print(f"wrote {dest} ({len(svg)//1024} KB, {len(out)} icons); missing: {missing}")


if __name__ == "__main__":
    main(sys.argv[1])
