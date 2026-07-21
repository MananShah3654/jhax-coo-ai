"""PDF report generator using reportlab — branded for JHAX.
Outputs an executive 1-2 page PDF a restaurant owner can WhatsApp / email instantly."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

ORANGE = colors.HexColor("#FF6B35")
SLATE  = colors.HexColor("#1E293B")
MUTED  = colors.HexColor("#64748B")
GREEN  = colors.HexColor("#22C55E")
RED    = colors.HexColor("#EF4444")
LIGHT  = colors.HexColor("#F8FAFC")


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "JpTitle", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=SLATE, spaceAfter=4,
    )
    sub = ParagraphStyle(
        "JpSub", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, textColor=MUTED, spaceAfter=14,
    )
    eyebrow = ParagraphStyle(
        "JpEyebrow", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=8, textColor=ORANGE,
        leading=10, spaceAfter=2,
    )
    h2 = ParagraphStyle(
        "JpH2", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=14, textColor=SLATE,
        leading=18, spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        "JpBody", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, leading=14, textColor=SLATE,
    )
    return {"title": title, "sub": sub, "eyebrow": eyebrow, "h2": h2, "body": body}


def _kpi_row(items: List[Dict[str, str]]) -> Table:
    """Tile-style KPI row."""
    cells = [[Paragraph(f"<font size=7 color='#94A3B8'><b>{i['label'].upper()}</b></font>"
                        f"<br/><font size=18 color='#0F172A'><b>{i['value']}</b></font>"
                        + (f"<br/><font size=8 color='#64748B'>{i['sub']}</font>" if i.get("sub") else ""),
                        ParagraphStyle("k", fontName="Helvetica", leading=22))
              for i in items]]
    t = Table(cells, colWidths=[(7.0 / len(items)) * inch] * len(items))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _section(title: str, st):
    return [Paragraph(title, st["h2"])]


def _on_first_page(canvas, doc):
    # Brand chip top-right
    canvas.saveState()
    canvas.setFillColor(ORANGE)
    canvas.roundRect(LETTER[0] - 1.6 * inch, LETTER[1] - 0.55 * inch,
                     1.2 * inch, 0.32 * inch, 4, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(LETTER[0] - 1.0 * inch, LETTER[1] - 0.38 * inch,
                             "JHAX")
    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.6 * inch, 0.4 * inch,
                      f"Generated {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}")
    canvas.drawRightString(LETTER[0] - 0.6 * inch, 0.4 * inch,
                           "One Question. One Answer. One Action.")
    canvas.restoreState()


def build_report_pdf(
    report_type: str,
    owner: Dict,
    today: Dict,
    health: Dict,
    branches: List[Dict],
    menu: List[Dict],
    customers_summary: Dict,
    forecast_data: Dict,
    briefing: Dict,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.7 * inch, bottomMargin=0.6 * inch,
        title=f"JHAX — {report_type.title()} Report",
    )
    st = _styles()
    story = []

    # Header
    story.append(Paragraph(f"{report_type.title()} Report", st["title"]))
    story.append(Paragraph(
        f"<b>{owner.get('restaurant','Restaurant')}</b> &nbsp;·&nbsp; "
        f"prepared for {owner.get('name','Owner')}", st["sub"]))

    # Top-line KPIs
    delta = today.get("vs_yesterday_pct", 0) or 0
    story += _section("Today at a glance", st)
    story.append(_kpi_row([
        {"label": "Revenue",  "value": f"${today['revenue']:,.0f}",
         "sub": f"{'+' if delta > 0 else ''}{delta:.1f}% vs yesterday"},
        {"label": "Orders",   "value": f"{today['orders']}"},
        {"label": "Avg Order","value": f"${today['avg_order_value']:.2f}"},
        {"label": "Tips",     "value": f"${today['tips']:,.0f}"},
        {"label": "Health",   "value": f"{health['score']}/100",
         "sub": health["state"].upper()},
    ]))

    # Briefing highlight
    if briefing:
        story += _section("Executive Briefing", st)
        story.append(Paragraph(
            f"Yesterday: <b>${briefing['yesterday_revenue']:,.0f}</b> on "
            f"<b>{briefing['yesterday_orders']}</b> orders "
            f"({'+' if briefing['growth_pct'] > 0 else ''}{briefing['growth_pct']}% DoD). "
            f"Top seller <b>{briefing['top_seller']}</b>. "
            f"Best branch <b>{briefing['best_branch']}</b>.",
            st["body"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<b>Recommended action:</b> {briefing['recommended_action']}", st["body"]))
        story.append(Paragraph(
            f"<b>Expected opportunity:</b> "
            f"<font color='#16A34A'>+${briefing['expected_opportunity']:,.0f}/week</font>",
            st["body"]))

    # Branches table
    story += _section("Branch performance (last 7 days)", st)
    rows = [["Branch", "Manager", "Revenue", "Orders", "AOV", "Growth"]]
    for b in branches:
        rows.append([b["name"], b["manager"],
                     f"${b['revenue']:,.0f}", str(b["orders"]),
                     f"${b['avg_order_value']:.2f}",
                     f"{'+' if b['growth_pct'] >= 0 else ''}{b['growth_pct']:.1f}%"])
    t = Table(rows, colWidths=[1.5, 1.0, 1.1, 0.8, 0.9, 0.9])
    t = Table(rows, colWidths=[1.4 * inch, 1.0 * inch, 1.1 * inch, 0.8 * inch, 0.9 * inch, 0.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), SLATE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("LINEBELOW",  (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TEXTCOLOR",  (-1, 1), (-1, -1), GREEN),
        ("ALIGN",      (2, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    # Color worst branch's growth red
    worst_idx = min(range(len(branches)), key=lambda i: branches[i]["growth_pct"]) + 1
    t.setStyle(TableStyle([("TEXTCOLOR", (-1, worst_idx), (-1, worst_idx), RED)]))
    story.append(t)

    # Menu top/bottom
    story += _section("Menu — top sellers (30d)", st)
    rows = [["Item", "Category", "Units", "Revenue", "Margin"]]
    for m in menu[:5]:
        rows.append([m["name"], m["category"], str(m["units_sold"]),
                     f"${m['revenue']:,.0f}", f"{m['margin_pct']}%"])
    t = Table(rows, colWidths=[2.0 * inch, 1.2 * inch, 0.8 * inch, 1.1 * inch, 0.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # Customers + Forecast row (compact)
    story += _section("Customers & forecast", st)
    story.append(_kpi_row([
        {"label": "Total customers", "value": f"{customers_summary['total_customers']}"},
        {"label": "VIPs",            "value": f"{customers_summary['vip_count']}"},
        {"label": "At risk",         "value": f"{customers_summary['at_risk_count']}"},
        {"label": "Repeat rate",     "value": f"{customers_summary['repeat_rate_pct']}%"},
        {"label": "30d forecast",    "value": f"${forecast_data['projected_revenue']:,.0f}",
         "sub": f"{forecast_data['confidence']}% confidence"},
    ]))

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_first_page)
    return buf.getvalue()
