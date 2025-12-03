import os
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import datetime

def generate_invoice_number(user_id, invoice_date):
    """Generate unique invoice number"""
    date_str = invoice_date.strftime('%Y%m%d')
    return f"INV-{user_id:05d}-{date_str}"

def generate_invoice_pdf(invoice):
    """
    Generate a professional PDF invoice
    
    Args:
        invoice: Invoice model instance
        
    Returns:
        BytesIO: PDF file content
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a73e8'),
        spaceAfter=30,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
    )
    
    normal_style = styles['Normal']
    
    # Add company/header information
    elements.append(Paragraph("SUBSCRIPTION ENGINE", title_style))
    elements.append(Paragraph("Invoice", heading_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Invoice details
    invoice_info = [
        ["Invoice Number:", invoice.invoice_number],
        ["Invoice Date:", invoice.invoice_date.strftime('%B %d, %Y')],
        ["Status:", invoice.status.upper()],
        ["", ""],
        ["Bill To:", ""],
        ["Customer:", invoice.user.username],
        ["Email:", invoice.user.email],
    ]
    
    if invoice.subscription:
        invoice_info.append(["Plan:", invoice.subscription.plan.name])
    
    invoice_info.extend([
        ["", ""],
        ["Billing Period:", ""],
        ["From:", invoice.period_start.strftime('%B %d, %Y')],
        ["To:", invoice.period_end.strftime('%B %d, %Y')],
    ])
    
    info_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Line items header
    elements.append(Paragraph("Usage Details", heading_style))
    elements.append(Spacer(1, 0.1 * inch))
    
    # Create line items table
    items_data = [['Feature', 'Used', 'Limit', 'Status']]
    
    for item in invoice.items:
        feature = item.get('feature', 'N/A')
        used = str(item.get('used', 0))
        limit = str(item.get('limit', 0)) if item.get('limit', -1) != -1 else 'Unlimited'
        
        # Calculate status
        if item.get('limit', -1) == -1:
            status = 'Unlimited'
        elif item.get('used', 0) >= item.get('limit', 0):
            status = 'Limit Reached'
        else:
            remaining = item.get('limit', 0) - item.get('used', 0)
            status = f'{remaining} Remaining'
        
        items_data.append([feature, used, limit, status])
    
    items_table = Table(items_data, colWidths=[2.5*inch, 1*inch, 1.2*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body styling
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Totals
    totals_data = [
        ['Subtotal:', f'₹{invoice.subtotal:.2f}'],
        ['Tax:', f'₹{invoice.tax:.2f}'],
        ['Total:', f'₹{invoice.total:.2f}'],
    ]
    
    totals_table = Table(totals_data, colWidths=[4.5*inch, 1.7*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor('#cccccc')),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#1a73e8')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e8f0fe')),
        ('FONTSIZE', (0, 2), (-1, 2), 13),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(totals_table)
    elements.append(Spacer(1, 0.5 * inch))
    
    # Footer
    footer_text = """
    <para align=center>
    <font size=9 color="#666666">
    Thank you for your business!<br/>
    For questions about this invoice, please contact support.<br/>
    <br/>
    This is a computer-generated invoice and does not require a signature.
    </font>
    </para>
    """
    elements.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf
