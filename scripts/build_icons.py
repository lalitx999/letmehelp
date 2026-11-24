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


# ไอคอนที่ Bootstrap Icons ไม่มี (วาดเอง)
CUSTOM = [
    '<symbol id="volume-up" viewBox="0 0 16 16"><path d="M1.5 5.75h2.6L7.6 2.9a.5.5 0 0 1 .82.39v9.42a.5.5 0 0 1-.82.39L4.1 10.25H1.5a.5.5 0 0 1-.5-.5v-3.5a.5.5 0 0 1 .5-.5Z"/><path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M10.6 5.6a3.4 3.4 0 0 1 0 4.8M12.6 3.6a6.2 6.2 0 0 1 0 8.8"/></symbol>',
    '<symbol id="volume-mute" viewBox="0 0 16 16"><path d="M1.5 5.75h2.6L7.6 2.9a.5.5 0 0 1 .82.39v9.42a.5.5 0 0 1-.82.39L4.1 10.25H1.5a.5.5 0 0 1-.5-.5v-3.5a.5.5 0 0 1 .5-.5Z"/><path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="m10.8 6 4 4m0-4-4 4"/></symbol>',
    '<symbol id="fullscreen" viewBox="0 0 16 16"><path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M1.75 5.5V1.75H5.5m5 0h3.75V5.5m0 5v3.75H10.5m-5 0H1.75V10.5"/></symbol>',
    '<symbol id="fullscreen-exit" viewBox="0 0 16 16"><path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M5.5 1.75V5.5H1.75m12.5 0H10.5V1.75m0 12.5V10.5h3.75m-12.5 0H5.5v3.75"/></symbol>',
    '<symbol id="lemon8" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 .5a3.6 3.6 0 0 0-2.4 6.3A4.1 4.1 0 0 0 8 15.5a4.1 4.1 0 0 0 2.4-8.7A3.6 3.6 0 0 0 8 .5Zm0 1.8a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Zm0 5.4a2.3 2.3 0 1 1 0 4.6 2.3 2.3 0 0 1 0-4.6Z"/></symbol>',
]


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
    out += CUSTOM
    svg = '<svg xmlns="http://www.w3.org/2000/svg">' + "".join(out) + "</svg>"
    dest = Path(__file__).resolve().parent.parent / "static/vendor/bootstrap-icons/icons.svg"
    dest.write_text(svg)
    print(f"wrote {dest} ({len(svg)//1024} KB, {len(out)} icons); missing: {missing}")


if __name__ == "__main__":
    main(sys.argv[1])
