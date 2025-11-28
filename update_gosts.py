# update_gosts.py
from database import get_session, GOST


def update_gosts():
    session = get_session()

    # Добавляем ГОСТы
    gosts_data = [
        {
            "name": "ГОСТ 7.9-95",
            "description": "Реферат и аннотация",
            "client_type_for": "all",
        },
        {
            "name": "ГОСТ 7.32-2001",
            "description": "Отчет о научно-исследовательской работе",
            "client_type_for": "all",
        },
        {
            "name": "ГОСТ 7.0.5-2008",
            "description": "Библиографическая ссылка",
            "client_type_for": "all",
        },
    ]

    for gost_data in gosts_data:
        # Проверяем, существует ли уже такой ГОСТ
        existing_gost = session.query(GOST).filter_by(name=gost_data["name"]).first()
        if not existing_gost:
            new_gost = GOST(
                name=gost_data["name"],
                description=gost_data["description"],
                client_type_for=gost_data["client_type_for"],
            )
            session.add(new_gost)
            print(f"Добавлен ГОСТ: {gost_data['name']}")
        else:
            print(f"ГОСТ уже существует: {gost_data['name']}")

    session.commit()
    session.close()
    print("Обновление ГОСТов завершено!")


if __name__ == "__main__":
    update_gosts()
