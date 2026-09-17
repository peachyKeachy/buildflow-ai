# project data and BuildFlow Business Logic

projects = [
    {
        "id": 101,
        "name": "Naples Medical Center",
        "status": "active",
        "rfis": [
            {
                "id": 1,
                "title": "Electrical routing conflict",
                "days_open": 12,
                "is_blocking": True
            },
            {
                "id": 2,
                "title": "Door hardware clarification",
                "days_open": 3,
                "is_blocking": False
            },
            {
                "id": 3,
                "title": "Mechanical duct conflict",
                "days_open": 8,
                "is_blocking": True
            }
        ]
    }
]


# functions

def get_project_by_id(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return project

    return None

def is_critical_rfi(rfi: dict) -> bool:
    return rfi["is_blocking"] and rfi["days_open"] > 7


def get_critical_rfis(rfis: list) -> list:
    critical_rfis = []

    for rfi in rfis:
        if is_critical_rfi(rfi):
            critical_rfis.append(rfi)

    return critical_rfis


def get_blocking_rfis(rfis: list) -> list:
    blocking_rfis = []

    for rfi in rfis:
        if rfi["is_blocking"]:
            blocking_rfis.append(rfi)

    return blocking_rfis


def get_project_summary(project: dict) -> dict:
    summary = {
        "project_name": project["name"],
        "total_rfis": len(project["rfis"]),
        "critical_rfis": len(get_critical_rfis(project["rfis"])),
        "blocking_rfis": len(get_blocking_rfis(project["rfis"]))
    }

    return summary

def get_project_rfis(project: dict) -> list:
    return project["rfis"]