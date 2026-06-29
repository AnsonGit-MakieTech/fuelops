import csv
from io import BytesIO, StringIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPORT_TYPES = {
    "comprehensive": "Comprehensive Operations Report",
    "daily_sales": "Daily Sales and Reconciliation",
    "performance": "Monthly Performance Report",
    "inventory": "Inventory Movement Report",
    "deliveries": "Fuel Delivery and Purchase Report",
    "expenses": "Expense Breakdown Report",
    "variance": "Cash Variance Report",
}

REPORT_FORMATS = {"pdf", "csv", "print"}


def amount(value):
    return f"PHP {value:,.2f}"


def volume(value):
    return f"{value:,.3f} L"


def _summary_rows(summary):
    return [
        ["Liters sold", volume(summary["monthly_liters"])],
        ["Gross sales", amount(summary["monthly_expected_sales"])],
        ["Fuel cost", amount(summary["monthly_fuel_cost"])],
        ["Gross profit", amount(summary["gross_profit"])],
        ["Expenses", amount(summary["monthly_expenses"])],
        ["Net profit", amount(summary["net_profit"])],
        ["Delivered liters", volume(summary["delivery_liters"])],
        ["Delivery cost", amount(summary["delivery_cost"])],
        ["Cash shortage", amount(summary["monthly_shortage"])],
        ["Cash overage", amount(summary["monthly_overage"])],
    ]


def build_sections(report_type, report):
    sections = {
        "summary": {
            "title": "Performance Summary",
            "columns": ["Metric", "Value"],
            "rows": _summary_rows(report["summary"]),
        },
        "daily_sales": {
            "title": "Approved Sales",
            "columns": ["Date", "Liters", "Expected", "Collected", "Shortage", "Overage"],
            "rows": [
                [
                    operation.operation_date.isoformat(),
                    volume(operation.total_liters_sold),
                    amount(operation.total_expected_sales),
                    amount(operation.total_collections),
                    amount(operation.shortage),
                    amount(operation.overage),
                ]
                for operation in report["daily_operations"]
            ],
        },
        "products": {
            "title": "Fuel Product Performance",
            "columns": ["Product", "Code", "Liters", "Sales", "Fuel Cost", "Gross Profit"],
            "rows": [
                [
                    product["name"],
                    product["code"],
                    volume(product["liters"]),
                    amount(product["sales"]),
                    amount(product["fuel_cost"]),
                    amount(product["gross_profit"]),
                ]
                for product in report["product_totals"]
            ],
        },
        "inventory": {
            "title": "Inventory Movements",
            "columns": ["Date", "Type", "Tank", "Liters", "Reference"],
            "rows": [
                [
                    movement["date"].isoformat(),
                    movement["type"],
                    movement["tank_name"],
                    volume(movement["movement_liters"]),
                    movement["reference"],
                ]
                for movement in report["inventory_movements"]
            ],
        },
        "deliveries": {
            "title": "Fuel Deliveries",
            "columns": ["Date", "Product", "Tank", "Supplier", "Liters", "Cost/L", "Total", "Invoice"],
            "rows": [
                [
                    delivery.delivery_date.isoformat(),
                    delivery.fuel_product.name,
                    delivery.tank.name,
                    delivery.supplier.name,
                    volume(delivery.liters_delivered),
                    amount(delivery.cost_per_liter),
                    amount(delivery.total_cost),
                    delivery.invoice_number or "-",
                ]
                for delivery in report["deliveries"]
            ],
        },
        "expenses": {
            "title": "Expenses",
            "columns": ["Date", "Category", "Amount", "Vendor", "Reference", "Paid By"],
            "rows": [
                [
                    expense.expense_date.isoformat(),
                    expense.category.name,
                    amount(expense.amount),
                    expense.vendor or "-",
                    expense.reference_number or "-",
                    expense.paid_by or "-",
                ]
                for expense in report["expenses"]
            ],
        },
        "variance": {
            "title": "Cash Variance",
            "columns": ["Date", "Expected", "Collected", "Shortage", "Overage"],
            "rows": [
                [
                    operation.operation_date.isoformat(),
                    amount(operation.total_expected_sales),
                    amount(operation.total_collections),
                    amount(operation.shortage),
                    amount(operation.overage),
                ]
                for operation in report["daily_operations"]
            ],
        },
    }
    mapping = {
        "comprehensive": ["summary", "daily_sales", "products", "deliveries", "expenses", "inventory", "variance"],
        "daily_sales": ["daily_sales"],
        "performance": ["summary", "products"],
        "inventory": ["inventory"],
        "deliveries": ["deliveries"],
        "expenses": ["expenses"],
        "variance": ["variance"],
    }
    return [sections[key] for key in mapping[report_type]]


def report_metadata(station, report_type, date_from, date_to, month_value, user):
    return {
        "title": REPORT_TYPES[report_type],
        "station": station.name,
        "station_address": station.address,
        "date_range": f"{date_from.isoformat()} to {date_to.isoformat()}",
        "month": month_value,
        "generated_by": user.get_full_name() or user.get_username(),
        "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M %Z"),
    }


def report_filename(station, report_type, extension):
    station_slug = "".join(character.lower() if character.isalnum() else "-" for character in station.name)
    station_slug = "-".join(part for part in station_slug.split("-") if part) or "station"
    return f"fuelops-{station_slug}-{report_type}-{timezone.localdate().isoformat()}.{extension}"


def _csv_safe(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def render_csv(metadata, sections):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([metadata["title"]])
    writer.writerow(["Station", _csv_safe(metadata["station"])])
    writer.writerow(["Date range", metadata["date_range"]])
    writer.writerow(["Monthly period", metadata["month"]])
    writer.writerow(["Generated by", _csv_safe(metadata["generated_by"])])
    writer.writerow(["Generated at", metadata["generated_at"]])
    for section in sections:
        writer.writerow([])
        writer.writerow([section["title"]])
        writer.writerow(section["columns"])
        for row in section["rows"]:
            writer.writerow([_csv_safe(value) for value in row])
        if not section["rows"]:
            writer.writerow(["No records"])
    return output.getvalue()


def render_pdf(metadata, sections):
    output = BytesIO()
    page_size = landscape(A4)
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=metadata["title"],
        author=metadata["generated_by"],
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FuelOpsTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#111827"),
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    heading_style = ParagraphStyle(
        "FuelOpsHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#111827"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    cell_style = ParagraphStyle(
        "FuelOpsCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1F2937"),
    )
    header_style = ParagraphStyle(
        "FuelOpsHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = []
    logo_path = Path(settings.BASE_DIR) / "static" / "assets" / "fuelops-logo-with-text-rectangle.png"
    if logo_path.exists():
        logo = Image(str(logo_path), width=42 * mm, height=12 * mm)
        story.append(logo)
        story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(escape(metadata["title"]), title_style))
    metadata_rows = [
        ["Station", metadata["station"], "Date range", metadata["date_range"]],
        ["Address", metadata["station_address"] or "-", "Monthly period", metadata["month"]],
        ["Generated by", metadata["generated_by"], "Generated at", metadata["generated_at"]],
    ]
    metadata_table = Table(
        [[Paragraph(f"<b>{escape(str(value))}</b>" if index % 2 == 0 else escape(str(value)), cell_style) for index, value in enumerate(row)] for row in metadata_rows],
        colWidths=[24 * mm, 86 * mm, 28 * mm, 100 * mm],
    )
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(metadata_table)
    story.append(Spacer(1, 3 * mm))

    available_width = page_size[0] - document.leftMargin - document.rightMargin
    for index, section in enumerate(sections):
        if index and len(sections) > 4 and index in {3, 5}:
            story.append(PageBreak())
        story.append(Paragraph(escape(section["title"]), heading_style))
        rows = [section["columns"], *section["rows"]]
        if not section["rows"]:
            rows.append(["No records", *([""] * (len(section["columns"]) - 1))])
        table_rows = []
        for row_index, row in enumerate(rows):
            style = header_style if row_index == 0 else cell_style
            table_rows.append([Paragraph(escape(str(value)), style) for value in row])
        table = LongTable(
            table_rows,
            repeatRows=1,
            colWidths=[available_width / len(section["columns"])] * len(section["columns"]),
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#F59E0B"))
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, 10 * mm, page_size[0] - doc.rightMargin, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(doc.leftMargin, 6 * mm, f"FuelOps | {metadata['station']}")
        canvas.drawRightString(page_size[0] - doc.rightMargin, 6 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
