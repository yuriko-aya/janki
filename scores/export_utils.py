"""Utility functions for exporting team standings to CSV and PDF formats."""
import csv
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


def export_standings_to_csv(team, standings, month=None, year=None, is_yearly=False):
    """Export team standings to CSV format.
    
    Args:
        team: Team object
        standings: List of Member objects with calculated scores
        month: Optional month number (1-12)
        year: Optional year number
        is_yearly: If True, export all year data instead of monthly
    
    Returns:
        HttpResponse with CSV file attachment
    """
    response = HttpResponse(content_type='text/csv')
    
    # Generate filename
    if is_yearly and year:
        filename = f"{team.slug}_standings_{year}.csv"
    elif month and year:
        filename = f"{team.slug}_standings_{year}_{month:02d}.csv"
    else:
        filename = f"{team.slug}_standings.csv"
    
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Header row
    if is_yearly:
        writer.writerow([
            f'{team.name} - Standings ({year})',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''
        ])
    elif month and year:
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        writer.writerow([
            f'{team.name} - Standings ({month_names[month]} {year})',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''
        ])
    else:
        writer.writerow([f'{team.name} - Standings', '', '', '', '', '', '', '', '', ''])
    
    writer.writerow([])  # Blank row
    
    # Column headers
    writer.writerow([
        'Rank',
        'Player Name',
        'Total Score',
        'Games Played',
        'Average/Game',
        'Avg Placement',
        '1st Place',
        '2nd Place',
        '3rd Place',
        '4th Place',
        'Chombo Count'
    ])
    
    # Data rows
    for rank, member in enumerate(standings, start=1):
        if is_yearly:
            # Use yearly stats
            writer.writerow([
                rank,
                member.name,
                f"{member.yearly_total:.2f}",
                member.yearly_games,
                f"{member.yearly_average:.2f}",
                f"{member.yearly_avg_placement:.2f}" if member.yearly_avg_placement else '',
                member.yearly_first_place,
                member.yearly_second_place,
                member.yearly_third_place,
                member.yearly_fourth_place,
                member.yearly_chombo_count
            ])
        else:
            # Use monthly stats
            writer.writerow([
                rank,
                member.name,
                f"{member.monthly_total:.2f}",
                member.monthly_games,
                f"{member.monthly_average:.2f}",
                f"{member.monthly_avg_placement:.2f}" if member.monthly_avg_placement else '',
                member.monthly_first_place,
                member.monthly_second_place,
                member.monthly_third_place,
                member.monthly_fourth_place,
                member.monthly_chombo_count
            ])
    
    return response


def export_standings_to_pdf(team, standings, month=None, year=None, is_yearly=False):
    """Export team standings to PDF format.
    
    Args:
        team: Team object
        standings: List of Member objects with calculated scores
        month: Optional month number (1-12)
        year: Optional year number
        is_yearly: If True, export all year data instead of monthly
    
    Returns:
        HttpResponse with PDF file attachment
    """
    response = HttpResponse(content_type='application/pdf')
    
    # Generate filename
    if is_yearly and year:
        filename = f"{team.slug}_standings_{year}.pdf"
    elif month and year:
        filename = f"{team.slug}_standings_{year}_{month:02d}.pdf"
    else:
        filename = f"{team.slug}_standings.pdf"
    
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create PDF document
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Title
    if is_yearly and year:
        title = f"{team.name} - Standings ({year})"
    elif month and year:
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        title = f"{team.name} - Standings ({month_names[month]} {year})"
    else:
        title = f"{team.name} - Standings"
    
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Table data
    data = [
        ['Rank', 'Player', 'Total', 'Games', 'Avg/Game', 'Avg Plc', '1st', '2nd', '3rd', '4th', 'Chombo']
    ]
    
    for rank, member in enumerate(standings, start=1):
        if is_yearly:
            # Use yearly stats
            data.append([
                str(rank),
                member.name,
                f"{member.yearly_total:.1f}",
                str(member.yearly_games),
                f"{member.yearly_average:.1f}",
                f"{member.yearly_avg_placement:.1f}" if member.yearly_avg_placement else '-',
                str(member.yearly_first_place),
                str(member.yearly_second_place),
                str(member.yearly_third_place),
                str(member.yearly_fourth_place),
                str(member.yearly_chombo_count)
            ])
        else:
            # Use monthly stats
            data.append([
                str(rank),
                member.name,
                f"{member.monthly_total:.1f}",
                str(member.monthly_games),
                f"{member.monthly_average:.1f}",
                f"{member.monthly_avg_placement:.1f}" if member.monthly_avg_placement else '-',
                str(member.monthly_first_place),
                str(member.monthly_second_place),
                str(member.monthly_third_place),
                str(member.monthly_fourth_place),
                str(member.monthly_chombo_count)
            ])
    
    # Create table
    table = Table(data, colWidths=[
        0.5 * inch,  # Rank
        1.8 * inch,  # Player
        0.7 * inch,  # Total
        0.6 * inch,  # Games
        0.8 * inch,  # Avg/Game
        0.7 * inch,  # Avg Plc
        0.4 * inch,  # 1st
        0.4 * inch,  # 2nd
        0.4 * inch,  # 3rd
        0.4 * inch,  # 4th
        0.6 * inch   # Chombo
    ])
    
    # Table style
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#595858")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Rank column centered
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Player name left-aligned
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # All other columns centered
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
       
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data and write to response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response
