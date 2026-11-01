"""
PDF Incident Report Generation Service.
Generates professional, printable disaster incident situational reports
using ReportLab with zero external paid services or commercial binaries.
"""

import io
from datetime import datetime, timezone
from typing import Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_incident_pdf_report(incident: Dict[str, Any], exposure: Dict[str, Any], summary_data: Dict[str, Any]) -> bytes:
    """
    Renders an emergency incident report as PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    navy_dark = colors.HexColor("#060B18")
    navy_blue = colors.HexColor("#111E3E")
    accent_cyan = colors.HexColor("#0284C7")
    gray_light = colors.HexColor("#F1F5F9")
    gray_muted = colors.HexColor("#64748B")
    
    crit_color = colors.HexColor("#DC2626")
    if incident.get("priority_level") == "HIGH":
        crit_color = colors.HexColor("#EA580C")
    elif incident.get("priority_level") in ("MEDIUM", "LOW"):
        crit_color = colors.HexColor("#0284C7")

    # Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=navy_blue
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=gray_muted
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=navy_blue,
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=navy_dark
    )
    bullet_style = ParagraphStyle(
        "BulletDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=navy_dark,
        leftIndent=12
    )

    story = []

    # 1. Document Header Banner
    header_data = [
        [
            Paragraph("<b>DISASTER INTELLIGENCE PLATFORM</b><br/><font size='8' color='#64748B'>Autonomous Multi-Hazard Monitoring & Prioritization System</font>", title_style),
            Paragraph(f"<b>REPORT CLASSIFICATION</b><br/><font size='12' color='{crit_color.hexval()}'><b>{incident.get('priority_level', 'ACTIVE')} PRIORITY</b></font><br/><font size='7.5' color='#64748B'>Score: {incident.get('priority_score', 0):.1f}/100</font>", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[380, 160])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_cyan, spaceBefore=4, spaceAfter=10))

    # 2. Incident Overview Table
    uid = incident.get("incident_uid", "INC-000")
    hazard = incident.get("hazard_type", "MULTI_HAZARD")
    lat = incident.get("centroid_lat", 0.0)
    lon = incident.get("centroid_lon", 0.0)
    area = incident.get("affected_area_sqkm", 0.0)
    conf = incident.get("confidence_score", 0.85) * 100.0
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    meta_data = [
        ["Incident UID:", uid, "Observation Timestamp:", now_utc],
        ["Hazard Domain:", hazard, "Centroid Coordinates:", f"[{lat:.4f}, {lon:.4f}]"],
        ["Incident Status:", incident.get("status", "ACTIVE"), "Perimeter Footprint:", f"~{area:.1f} sq km"],
        ["Priority Score:", f"{incident.get('priority_score', 0):.1f} / 100", "Satellite Confidence:", f"{conf:.0f}%"]
    ]
    meta_table = Table(meta_data, colWidths=[105, 165, 130, 140])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), gray_light),
        ("TEXTCOLOR", (0, 0), (-1, -1), navy_dark),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Executive Situational Brief
    story.append(Paragraph("1. Executive Situational Assessment", section_heading))
    exec_text = summary_data.get("executive_summary", incident.get("summary", "No summary available."))
    story.append(Paragraph(exec_text, body_style))
    story.append(Spacer(1, 8))

    # 4. Multi-Hazard Earth Observation Evidence
    story.append(Paragraph("2. Earth Observation Satellite Telemetry & Verification", section_heading))
    for highlight in summary_data.get("evidence_highlights", []):
        story.append(Paragraph(f"• {highlight}", bullet_style))
    story.append(Spacer(1, 8))

    # 5. Nearby Population & Infrastructure Exposure
    story.append(Paragraph("3. Population & Lifeline Exposure Analysis", section_heading))
    pop_exposed = exposure.get("estimated_population", 0)
    exp_score = exposure.get("exposure_score", 0.0)
    buffer_rad = exposure.get("buffer_radius_km", 10.0)

    exposure_table_data = [
        ["Buffer Search Radius:", f"{buffer_rad:.1f} km", "Human Exposure Index:", f"{exp_score:.1f} / 100"],
        ["Estimated Population:", f"{pop_exposed:,} persons", "Critical Infrastructure:", ", ".join(exposure.get("critical_facilities", ["Lifeline transport arteries"]))[:75]]
    ]
    exp_table = Table(exposure_table_data, colWidths=[120, 150, 130, 140])
    exp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(exp_table)
    story.append(Spacer(1, 8))

    # 6. Actionable Emergency Directives
    story.append(Paragraph("4. Recommended Emergency Response Directives", section_heading))
    for directive in summary_data.get("tactical_directives", []):
        story.append(Paragraph(f"• <b>Action Directive:</b> {directive}", bullet_style))
    story.append(Spacer(1, 14))

    # 7. Document Sign-off & Audit Notice
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#94A3B8"), spaceBefore=4, spaceAfter=6))
    notice_text = (
        "CONFIDENTIAL & SENSITIVE · OPERATIONAL DISASTER INTELLIGENCE PLATFORM · "
        "Generated autonomously via validated open Earth Observation data feeds (NASA FIRMS / Copernicus Sentinel). "
        "Intended for authorized emergency coordination and public safety dispatchers."
    )
    story.append(Paragraph(notice_text, subtitle_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

