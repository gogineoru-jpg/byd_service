@app.get("/act/pdf/{car_id}")
def generate_act_pdf(car_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    font_name = "Helvetica"
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        font_name = 'DejaVuSans'
    except Exception:
        pass

    styles = getSampleStyleSheet()
    
    # Кастомные стили
    title_style = ParagraphStyle(
        'ActTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=16,
        leading=20,
        alignment=1, # По центру
        spaceAfter=15
    )
    
    normal_style = ParagraphStyle(
        'ActNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14
    )
    
    bold_style = ParagraphStyle(
        'ActBold',
        parent=normal_style,
        fontName=font_name,
        fontSize=10,
        leading=14
    )

    # Заголовок документа
    elements.append(Paragraph(f"<b>Акт выполненных работ № {car.id}</b>", title_style))
    elements.append(Paragraph(f"<b>Филиал:</b> {car.filial or 'Филиал Сергели'}", normal_style))
    elements.append(Paragraph(f"<b>Дата приёмки:</b> {car.created_at.strftime('%d.%m.%Y %H:%M') if car.created_at else '-'}", normal_style))
    elements.append(Spacer(1, 10))

    # Информация о клиенте и автомобиле
    client_name = car.owner.full_name if car.owner else "Не указан"
    client_phone = car.owner.phone if car.owner else "Не указан"
    
    info_data = [
        [Paragraph(f"<b>Клиент:</b> {client_name}", normal_style), Paragraph(f"<b>Марка/Модель:</b> {car.brand_model}", normal_style)],
        [Paragraph(f"<b>Телефон:</b> {client_phone}", normal_style), Paragraph(f"<b>Гос. номер:</b> {car.plate_number or '-'}", normal_style)],
        [Paragraph(f"<b>VIN-код:</b> {car.vin_code or '-'}", normal_style), Paragraph(f"<b>Пробег:</b> {car.mileage} км", normal_style)]
    ]
    
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # Таблица работ и запчастей
    table_data = [
        ["№", "Наименование работ / Запчастей", "Кол-во", "Цена (сум)", "Сумма (сум)"]
    ]
    
    item_index = 1
    
    # Добавляем работы
    for work in car.works:
        table_data.append([
            str(item_index),
            Paragraph(f"[Работа] {work.description}", normal_style),
            "1",
            f"{work.price:,.2f}",
            f"{work.price:,.2f}"
        ])
        item_index += 1

    # Добавляем запчасти
    for part in car.parts:
        part_total = (part.price or 0) * (part.quantity or 1)
        table_data.append([
            str(item_index),
            Paragraph(f"[Запчасть] {part.name}", normal_style),
            str(part.quantity),
            f"{part.price:,.2f}",
            f"{part_total:,.2f}"
        ])
        item_index += 1

    # Если список пуст
    if len(table_data) == 1:
        table_data.append(["1", Paragraph("Нет добавленных работ или запчастей", normal_style), "0", "0.00", "0.00"])

    items_table = Table(table_data, colWidths=[30, 260, 50, 100, 100])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#333333")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), font_name),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 15))

    # Расчет итогов
    works_sum = sum(w.price for w in car.works if w.price)
    parts_sum = sum(p.price * p.quantity for p in car.parts if p.price and p.quantity)
    subtotal = works_sum + parts_sum
    
    discount_percent = min(10.0, max(0.0, car.discount_percent or 0.0))
    discount_amount = (subtotal * discount_percent) / 100.0
    total_sum = subtotal - discount_amount

    totals_data = [
        [Paragraph(f"<b>Итого по работам:</b>", normal_style), Paragraph(f"{works_sum:,.2f} сум", normal_style)],
        [Paragraph(f"<b>Итого по запчастям:</b>", normal_style), Paragraph(f"{parts_sum:,.2f} сум", normal_style)],
        [Paragraph(f"<b>Скидка ({discount_percent}%):</b>", normal_style), Paragraph(f"- {discount_amount:,.2f} сум", normal_style)],
        [Paragraph(f"<b>К оплате ИТОГО:</b>", bold_style), Paragraph(f"<b>{total_sum:,.2f} сум</b>", bold_style)]
    ]

    totals_table = Table(totals_data, colWidths=[400, 140])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(totals_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=act_{car.id}.pdf"}
    )

    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=zakaz_naryad_{car.id}.pdf"})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
